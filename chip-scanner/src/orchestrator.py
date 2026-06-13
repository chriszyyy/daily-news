"""漏斗编排器 — 每日运行三级状态机, 只对 Mid+High 算筹码。

流程:
  1. 刷新快照: 读最新 universe CSV → upsert 到 stocks (新代码入 Low)。
  2. Low→Mid 晋升 (廉价, 只用快照字段, 无逐只请求):
       低位 (change_60d_pct <= LOW_POS_60D) 且 流动性健康。
  3. 只对 Mid+High 池逐只算筹码 (几十~几百只, 不触发限流)。
  4. 筹码流转:
       Mid→High : SCR<0.10 且 获利<0.25 且 价≤成本
       High→Mid : 不再满足 High (但仍满足 Mid)
       Mid→Low  : 不再低位 / 筹码发散 (降级带冷却)
  5. 输出 High 池 CSV (送视觉终审) + 打印漏斗统计。

用法:
  python src/orchestrator.py [--universe PATH] [--throttle 0.8] [--max-mid N]
"""

from __future__ import annotations

import argparse
import os
import time
from datetime import datetime

import pandas as pd

import chip_calc
import state_db as db

# ---- Low→Mid 廉价预筛 (仅快照字段, 无逐只请求) ----
# 新策略: 不限低位。用"横盘整理度"作密集单峰的廉价代理:
#   60日涨跌幅绝对值越小 = 越横盘 = 筹码越收敛 = 越可能密集单峰。
CONSOLIDATION_MAX = 30.0   # |60日涨跌幅| <= 此值才视为横盘候选 (%)
MID_BUDGET = 300        # Mid+High 池总预算上限 → 筹码扫描永远 ≤ 此数, 不触发限流

# ---- 筹码晋升门槛 (核心: 单峰密集, 用 70% 集中度; 不看套牢/低位) ----
# SCR70 = 70% 筹码的价格带集中度, 越小越密集 (单峰)
MID_SCR70 = 0.12        # Mid 池密集度门槛 (待数据校准)
HIGH_SCR70 = 0.08       # High 池密集度门槛 (高度密集单峰)

# ---- 防抖 ----
MID_MIN_STAY = 2        # Mid 最少停留天数 (内不降级)
DEMOTE_COOLDOWN = 3     # 降级冷却天数

OUTPUT_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "output")


def latest_universe() -> str:
    files = sorted(f for f in os.listdir(OUTPUT_DIR)
                   if f.startswith("universe_") and f.endswith(".csv"))
    if not files:
        raise FileNotFoundError("未找到 universe_*.csv")
    return os.path.join(OUTPUT_DIR, files[-1])


def refresh_snapshot(conn, uni_path: str) -> tuple[int, int]:
    df = pd.read_csv(uni_path, dtype={"code": str})
    df["code"] = df["code"].str.zfill(6)
    rows = [{
        "code": r["code"], "name": r["name"], "price": r["price"],
        "change_60d_pct": r.get("change_60d_pct"),
        "turnover_yuan": r.get("turnover_yuan"),
        "float_mktcap": r.get("float_market_cap"),
        "turnover_ratio": r.get("成交额占流通比%"),
        "health": r.get("健康度"), "industry": r.get("industry"),
        "pe_ttm": r.get("pe_ttm"),
    } for _, r in df.iterrows()]
    n = db.upsert_snapshot(conn, rows)
    pruned = db.prune_absent(conn, set(df["code"]))
    return n, pruned


def promote_low_to_mid(conn) -> int:
    """廉价预筛 (仅快照字段) + 预算上限。

    新策略: 盈利(PE>0) + 横盘整理(筹码收敛代理), 不限低位。
    维持 Mid+High 总数 ≤ MID_BUDGET: 按 |60日涨跌幅| 升序(最横盘优先)补位。
    """
    cur_pool = (len(db.get_by_level(conn, "Mid"))
                + len(db.get_by_level(conn, "High")))
    slots = MID_BUDGET - cur_pool
    if slots <= 0:
        return 0

    candidates = []
    for row in db.get_by_level(conn, "Low"):
        if db.in_cooldown(row):
            continue
        # 剔除亏损公司: PE_ttm 必须 > 0 (无 PE 数据则跳过该股)
        pe = row["pe_ttm"] if "pe_ttm" in row.keys() else None
        if pe is None or pe <= 0:
            continue
        c60 = row["change_60d_pct"]
        if c60 is None or abs(c60) > CONSOLIDATION_MAX:
            continue
        candidates.append((abs(c60), row))

    # 最横盘 (|涨跌幅|最小) 优先 → 筹码最收敛
    candidates.sort(key=lambda x: x[0])
    promoted = 0
    for absc60, row in candidates[:slots]:
        db.transition(conn, row["code"], "Mid",
                      f"横盘候选 (|60d|={absc60:.1f}%, PE={row['pe_ttm']:.1f})")
        promoted += 1
    return promoted


def scan_chips_for(conn, rows, throttle: float) -> tuple[int, int]:
    """对给定行逐只算筹码并写库。返回 (成功, 失败)。"""
    ok = fail = 0
    cur = throttle
    streak = 0
    for i, row in enumerate(rows, 1):
        m = chip_calc.fetch_chip_latest(row["code"])
        if m is None:
            fail += 1
            streak += 1
            if streak >= 5:
                cur = min(cur * 1.5, 2.0)
                print(f"[chip] 连续失败, 节流→{cur:.2f}s, 冷却 20s", flush=True)
                time.sleep(20)
                streak = 0
        else:
            m["chip_date"] = datetime.now().strftime("%Y-%m-%d")
            db.update_chips(conn, row["code"], m)
            ok += 1
            streak = 0
            cur = max(cur * 0.95, throttle)
        if i % 50 == 0:
            print(f"[chip] {i}/{len(rows)}, 成功 {ok}, 失败 {fail}", flush=True)
        time.sleep(cur)
    return ok, fail


def apply_chip_transitions(conn) -> tuple[int, int]:
    """根据筹码密集度 (SCR70) 对 Mid/High 池晋升/降级。不看套牢/低位。"""
    promoted = demoted = 0
    pool = list(db.get_by_level(conn, "Mid")) + list(db.get_by_level(conn, "High"))
    for row in pool:
        scr70 = row["scr70"]
        lvl = row["level"]
        has_chip = scr70 is not None

        is_high = has_chip and scr70 < HIGH_SCR70   # 高度密集单峰
        is_mid = has_chip and scr70 < MID_SCR70     # 较密集

        if lvl == "Mid":
            if is_high:
                db.transition(conn, row["code"], "High",
                              f"密集晋升 (SCR70={scr70:.3f})")
                promoted += 1
            elif not is_mid and db.days_in_level(row) >= MID_MIN_STAY:
                db.transition(conn, row["code"], "Low",
                              "密集度不足降级", cooldown_days=DEMOTE_COOLDOWN)
                demoted += 1
        elif lvl == "High":
            if not is_high:
                if is_mid:
                    db.transition(conn, row["code"], "Mid", "不再满足 High 密集度")
                else:
                    db.transition(conn, row["code"], "Low",
                                  "筹码发散降级", cooldown_days=DEMOTE_COOLDOWN)
                demoted += 1
    return promoted, demoted


def export_high(conn) -> tuple[str, list[dict]]:
    """导出 High 池 + 形态终审 verdict。返回 (csv路径, 记录列表)。"""
    import morphology
    rows = db.get_by_level(conn, "High")
    recs = []
    for r in rows:
        morph = morphology.analyze(r["code"]) or {}
        recs.append({
            "code": r["code"], "name": r["name"], "price": r["price"],
            "平均成本": r["avg_cost"], "PE": r["pe_ttm"],
            "SCR70": r["scr70"], "带宽70": r["band70"], "SCR90": r["scr"],
            "获利比例": r["profit_ratio"],
            "90成本低": r["cost_low90"], "90成本高": r["cost_high90"],
            "verdict": morph.get("verdict", "?"),
            "峰数": morph.get("n_peaks"),
            "主峰占比": morph.get("主峰占比"),
            "industry": r["industry"], "chip_date": r["chip_date"],
        })
    # 排序: PASS > WEAK > FAIL, 同档按 SCR70 升序 (最密集优先)
    order = {"PASS": 0, "WEAK": 1, "FAIL": 2, "?": 3}
    recs.sort(key=lambda x: (order.get(x["verdict"], 9), x["SCR70"] or 9))
    df = pd.DataFrame(recs) if recs else pd.DataFrame()
    ts = datetime.now().strftime("%Y%m%d")
    path = os.path.join(OUTPUT_DIR, f"high_pool_{ts}.csv")
    df.to_csv(path, index=False, encoding="utf-8-sig")
    return path, recs


def run(universe: str | None = None, throttle: float = 0.8,
        max_mid: int = 0, notify_enabled: bool = True) -> list[dict]:
    """执行一次完整漏斗流程。返回 High 池记录 (含 verdict)。"""
    conn = db.connect()
    db.init_db(conn)

    uni = universe or latest_universe()
    n, pruned = refresh_snapshot(conn, uni)
    print(f"[snap] 刷新 {n} 只, 清理 {pruned} 只 | 来源 {os.path.basename(uni)}")
    print(f"[snap] 当前分布: {db.level_counts(conn)}")

    p_lm = promote_low_to_mid(conn)
    print(f"[funnel] Low→Mid 廉价晋升 {p_lm} 只 | 分布: {db.level_counts(conn)}")

    pool = list(db.get_by_level(conn, "Mid")) + list(db.get_by_level(conn, "High"))
    if max_mid:
        pool = pool[:max_mid]
    print(f"[chip] 待算筹码 {len(pool)} 只 (仅 Mid+High, 不扫全市场)")
    ok, fail = scan_chips_for(conn, pool, throttle)
    db.log_run(conn, "chip_scan", scanned=len(pool), success=ok, failed=fail)
    print(f"[chip] 完成 成功 {ok} / 失败 {fail}")

    p_c, d_c = apply_chip_transitions(conn)
    db.log_run(conn, "transition", promoted=p_c, demoted=d_c)
    print(f"[funnel] 筹码流转: 晋升 {p_c}, 降级 {d_c} | 分布: {db.level_counts(conn)}")

    path, recs = export_high(conn)
    high_n = db.level_counts(conn).get("High", 0)
    print(f"[output] High 池 {high_n} 只 → {path}")

    # 形态终审摘要
    passed = [r for r in recs if r["verdict"] in ("PASS", "WEAK")]
    for r in recs:
        print(f"  [{r['verdict']:<4}] {r['code']} {r['name']} "
              f"SCR70={r['SCR70']:.3f} 带宽70={r['带宽70']:.1%} "
              f"PE={r['PE']:.1f} 峰数={r['峰数']} 主峰占比={r.get('主峰占比')}")

    if notify_enabled:
        try:
            import notify
            import plot_chips
            charts = {}
            for r in passed:                       # 仅对入选标的画图
                cp = plot_chips.plot_one(r["code"], r["name"])
                if cp:
                    charts[r["code"]] = cp
            notify.send_daily(recs, passed, charts)
        except Exception as e:  # noqa: BLE001
            print(f"[notify] 通知失败 (不影响主流程): {e}")

    conn.close()
    return recs


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--universe", default=None)
    ap.add_argument("--throttle", type=float, default=0.8)
    ap.add_argument("--max-mid", type=int, default=0,
                    help="限制本轮筹码扫描数量 (0=全部 Mid+High)")
    ap.add_argument("--no-notify", action="store_true", help="跳过通知")
    args = ap.parse_args()
    run(universe=args.universe, throttle=args.throttle,
        max_mid=args.max_mid, notify_enabled=not args.no_notify)


if __name__ == "__main__":
    main()
