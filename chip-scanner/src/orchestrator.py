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
MID_BUDGET = 2000       # Mid+High 池上限 → 覆盖全部硬过滤后标的(~1974); 腾讯源稳, ~15分钟

# ---- High 池选择: 单峰(次峰比) + 密集(带宽70) + 抛弃套牢盘 ----
# 最终口径 (120日窗口, 经用户图形校准):
#   1) 单峰: 次峰/主峰高度比 <= SECOND_MAX (排除北京银行/邮储这种双峰)
#   2) 密集: 带宽70 <= BAND70_MAX (70%筹码价格带宽; 排除盛路这种…实测8.4%也算密集)
#   3) 抛弃套牢盘: 现价相对主峰 >= POS_MIN (现价≈主峰或在上方)
#   排序: 带宽70 升序 (越密集越靠前)
SECOND_MAX = 0.50       # 次峰/主峰 <= 0.5 (单峰判据; 上港0.12/盛路0.00 过, 北京0.99 弃)
BAND70_MAX = 0.09       # 带宽70 <= 9% (密集判据; 上港4.2%/盛路8.4% 均过)
POS_MIN = -0.05         # 现价 >= 主峰*0.95 (抛弃套牢盘)
HIGH_TOPN = 20          # High 池每日取 Top-N (送终审)

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
        "main_net_inflow": r.get("main_net_inflow"),
        "main_net_pct": r.get("main_net_pct"),
        "super_net_inflow": r.get("super_net_inflow"),
        "super_net_pct": r.get("super_net_pct"),
        "large_net_inflow": r.get("large_net_inflow"),
        "large_net_pct": r.get("large_net_pct"),
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
    """High 池选择: 单峰(次峰比) + 密集(带宽70) + 抛弃套牢盘 (120日窗口)。

    候选 = Mid+High 中同时满足:
      次峰比 <= SECOND_MAX (单峰), 带宽70 <= BAND70_MAX (密集),
      现价相对主峰 >= POS_MIN (非套牢)。
    排序 = 带宽70 升序 (越密集越靠前) 取 Top-N → High; 其余回 Mid。
    """
    pool = list(db.get_by_level(conn, "Mid")) + list(db.get_by_level(conn, "High"))

    qualified = []
    for row in pool:
        sec, band, pos = row["second_ratio"], row["band70"], row["near_peak"]
        if not (sec is not None and band is not None and pos is not None):
            continue
        if sec <= SECOND_MAX and band <= BAND70_MAX and pos >= POS_MIN:
            qualified.append((band, row))
    qualified.sort(key=lambda x: x[0])   # 带宽升序, 越密集越前

    high_codes = {r["code"] for _, r in qualified[:HIGH_TOPN]}

    promoted = demoted = 0
    for row in pool:
        lvl = row["level"]
        should_be_high = row["code"] in high_codes
        if should_be_high and lvl == "Mid":
            db.transition(conn, row["code"], "High",
                          f"单峰密集Top{HIGH_TOPN} (次峰比={row['second_ratio']:.2f}, "
                          f"带宽70={row['band70']:.1%})")
            promoted += 1
        elif not should_be_high and lvl == "High":
            if db.days_in_level(row) >= MID_MIN_STAY:
                db.transition(conn, row["code"], "Mid", "跌出单峰密集 Top-N")
                demoted += 1
    return promoted, demoted


def export_high(conn) -> tuple[str, list[dict]]:
    """导出 High 池 (单峰+密集 Top-N)。按带宽70 升序 (越密集越前)。"""
    rows = db.get_by_level(conn, "High")
    recs = []
    for r in rows:
        fund_confirmed = (
            (r["main_net_inflow"] or 0) > 0
            and ((r["super_net_inflow"] or 0) > 0 or (r["large_net_inflow"] or 0) > 0)
        )
        recs.append({
            "code": r["code"], "name": r["name"], "price": r["price"],
            "主峰价": r["avg_cost"], "PE": r["pe_ttm"],
            "次峰比": r["second_ratio"], "带宽70": r["band70"],
            "尖锐度": r["sharpness"], "主峰占比": r["dominance"],
            "距主峰": r["near_peak"],
            "资金确认": "是" if fund_confirmed else "否",
            "主力净流入亿": (round(r["main_net_inflow"] / 1e8, 2)
                         if r["main_net_inflow"] is not None else None),
            "主力净占比": r["main_net_pct"],
            "超大单净流入亿": (round(r["super_net_inflow"] / 1e8, 2)
                           if r["super_net_inflow"] is not None else None),
            "超大单净占比": r["super_net_pct"],
            "大单净流入亿": (round(r["large_net_inflow"] / 1e8, 2)
                         if r["large_net_inflow"] is not None else None),
            "大单净占比": r["large_net_pct"],
            "90成本低": r["cost_low90"], "90成本高": r["cost_high90"],
            "industry": r["industry"], "chip_date": r["chip_date"],
        })
    # 带宽70 升序 (越密集越靠前)
    recs.sort(key=lambda x: (x["带宽70"] if x["带宽70"] is not None else 9))
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
    print(f"[output] High 池 {high_n} 只 (单峰+密集, 带宽升序) → {path}")

    # 基本面增强: 补业绩(净利/营收同比, ROE) + 量价(量比/成交额)
    try:
        import enrich
        recs = enrich.enrich(recs)
        # 增强后重写 CSV (含业绩量价列)
        import pandas as _pd
        _pd.DataFrame(recs).to_csv(path, index=False, encoding="utf-8-sig")
        print("[enrich] 已补充业绩 + 量价")
    except Exception as e:  # noqa: BLE001
        print(f"[enrich] 增强失败 (不影响主流程): {e}")

    # High 池即为入选 (单峰 + 密集 + 非套牢)
    passed = recs
    for i, r in enumerate(recs, 1):
        print(f"  {i:>2}. {r['code']} {r['name']} "
              f"次峰比={r['次峰比']:.2f} 带宽70={r['带宽70']:.1%} "
              f"距主峰={r['距主峰']:+.1%} PE={r['PE']:.1f} "
              f"主力={r.get('主力净流入亿')}亿/{r.get('主力净占比')}% "
              f"净利同比={r.get('净利润同比')}% 量比={r.get('量比')}")

    if notify_enabled:
        try:
            import notify
            import plot_chips
            import overview
            charts = {}
            for r in passed[:HIGH_TOPN]:           # 对入选标的画图
                cp = plot_chips.plot_one(r["code"], r["name"])
                if cp:
                    charts[r["code"]] = cp
            ov = overview.build_overview(passed[:HIGH_TOPN])   # 拼总览图
            notify.send_daily(recs, passed, charts, overview_path=ov)
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
