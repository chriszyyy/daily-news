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
import math
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

# ---- 强趋势启动池: 补足"已脱离横盘、正在发动"的趋势票 ----
# 与单峰密集池并行, 不走 Low→Mid 横盘过滤; 用最新 K 线确认趋势启动。
TREND_TOPN = 30
TREND_SCAN_BUDGET = 250
TREND_MIN_60D = 30.0             # 60日涨幅较强, 说明不是横盘密集逻辑
TREND_MIN_MOM5 = 8.0             # 近5日涨幅 >= 8%
TREND_NEAR_HIGH20 = 0.95         # 当前价接近近20日高点
TREND_TURNOVER_FLOOR = 5e8       # 成交额 >= 5亿
TREND_THEME_TURNOVER_FLOOR = 2e9 # 主题大票成交额 >= 20亿
TREND_INDUSTRIES = ("半导体", "电子", "通信", "计算机", "光学", "元件")

# ---- 推盘观察池: 主力/超大单推价格的盘中异动提示, 不作为买入信号 ----
PUSH_TOPN = 20
PUSH_SCAN_BUDGET = 180
PUSH_TURNOVER_FLOOR = 5e8
PUSH_MIN_CHANGE = 3.0
PUSH_MIN_MAIN_NET_PCT = 5.0
PUSH_MIN_CLOSE_STRENGTH = 0.65

# ---- 热门板块过滤: 每日由 universe 快照动态统计 ----
HOT_SECTOR_TOPN = 12
HOT_SECTOR_CANDIDATE_TOPN = 30
HOT_SECTOR_MIN_COUNT = 3
HOT_SECTOR_KEYWORDS = (
    "半导体", "电子", "通信", "计算机", "光学", "元件",
    "电力", "电网", "自动化", "机器人", "通用设备", "专用设备",
)
DEFENSIVE_INDUSTRIES = (
    "银行", "电力", "铁路公路", "航运港口", "港口", "高速",
    "煤炭", "保险", "公用事业", "水务", "燃气",
)
OFFENSIVE_INDUSTRIES = (
    "半导体", "电子", "通信", "计算机", "光学", "元件",
    "电网", "机器人", "通用设备", "专用设备", "消费电子",
    "小金属", "工业金属", "新材料", "电池",
)

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
        industry = r["industry"] or ""
        fund_confirmed = (
            (r["main_net_inflow"] or 0) > 0
            and ((r["super_net_inflow"] or 0) > 0 or (r["large_net_inflow"] or 0) > 0)
        )
        if any(k in industry for k in OFFENSIVE_INDUSTRIES):
            style = "进攻单峰"
        elif any(k in industry for k in DEFENSIVE_INDUSTRIES):
            style = "防守单峰"
        else:
            style = "普通单峰"
        recs.append({
            "code": r["code"], "name": r["name"], "price": r["price"],
            "主峰价": r["avg_cost"], "PE": r["pe_ttm"],
            "次峰比": r["second_ratio"], "带宽70": r["band70"],
            "尖锐度": r["sharpness"], "主峰占比": r["dominance"],
            "距主峰": r["near_peak"],
            "单峰类型": style,
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
            "industry": industry, "chip_date": r["chip_date"],
        })
    # 带宽70 升序 (越密集越靠前)
    recs.sort(key=lambda x: (x["带宽70"] if x["带宽70"] is not None else 9))
    df = pd.DataFrame(recs) if recs else pd.DataFrame()
    ts = datetime.now().strftime("%Y%m%d")
    path = os.path.join(OUTPUT_DIR, f"high_pool_{ts}.csv")
    df.to_csv(path, index=False, encoding="utf-8-sig")
    return path, recs


def export_sector_heat(uni_path: str) -> tuple[str, pd.DataFrame, set[str]]:
    """按行业统计当日热度, 输出 sector_heat_YYYYMMDD.csv 并返回热门行业集合。"""
    ts = datetime.now().strftime("%Y%m%d")
    prev_files = sorted(
        f for f in os.listdir(OUTPUT_DIR)
        if f.startswith("sector_heat_") and f.endswith(".csv")
        and not f.endswith(f"{ts}.csv")
    )
    prev_heat = None
    if prev_files:
        try:
            prev_heat = pd.read_csv(os.path.join(OUTPUT_DIR, prev_files[-1]))
            prev_heat["昨日排名"] = range(1, len(prev_heat) + 1)
        except Exception:  # noqa: BLE001
            prev_heat = None

    df = pd.read_csv(uni_path, dtype={"code": str})
    for col in ("change_pct", "turnover_yuan", "volume_ratio"):
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
    if "industry" not in df.columns or df.empty:
        heat = pd.DataFrame()
        hot: set[str] = set()
    else:
        w = df[df["industry"].notna()].copy()
        rows = []
        for industry, g in w.groupby("industry"):
            if len(g) < HOT_SECTOR_MIN_COUNT:
                continue
            chg = g["change_pct"].dropna()
            turnover_ew = g["turnover_yuan"].fillna(0).sum() / 1e8
            up_ratio = float((chg > 0).mean()) if len(chg) else 0.0
            mean_chg = float(chg.mean()) if len(chg) else 0.0
            median_chg = float(chg.median()) if len(chg) else 0.0
            vol_ratio = float(g["volume_ratio"].dropna().mean()) if "volume_ratio" in g else 0.0
            theme_hit = any(k in str(industry) for k in HOT_SECTOR_KEYWORDS)
            heat_score = (
                median_chg * 1.2
                + mean_chg * 0.8
                + up_ratio * 6
                + math.log10(turnover_ew + 1) * 1.5
                + min(vol_ratio, 5) * 0.6
                + (1.5 if theme_hit else 0)
            )
            rows.append({
                "industry": industry,
                "股票数": int(len(g)),
                "平均涨幅": round(mean_chg, 2),
                "中位涨幅": round(median_chg, 2),
                "上涨占比": round(up_ratio, 3),
                "成交额亿": round(turnover_ew, 2),
                "平均量比": round(vol_ratio, 2),
                "主题匹配": theme_hit,
                "热度分": round(heat_score, 2),
            })
        heat = pd.DataFrame(rows).sort_values("热度分", ascending=False).reset_index(drop=True)
        heat["排名"] = range(1, len(heat) + 1)
        if prev_heat is not None and not prev_heat.empty:
            prev_cols = ["industry", "昨日排名", "热度分", "成交额亿", "中位涨幅", "上涨占比"]
            prev = prev_heat[[c for c in prev_cols if c in prev_heat.columns]].copy()
            prev = prev.rename(columns={
                "热度分": "昨日热度分",
                "成交额亿": "昨日成交额亿",
                "中位涨幅": "昨日中位涨幅",
                "上涨占比": "昨日上涨占比",
            })
            heat = heat.merge(prev, on="industry", how="left")
            heat["排名变化"] = (heat["昨日排名"] - heat["排名"]).where(heat["昨日排名"].notna())
            heat["热度变化"] = (heat["热度分"] - heat["昨日热度分"]).round(2)
            heat["成交额变化亿"] = (heat["成交额亿"] - heat["昨日成交额亿"]).round(2)
            heat["中位涨幅变化"] = (heat["中位涨幅"] - heat["昨日中位涨幅"]).round(2)
            heat["上涨占比变化"] = (heat["上涨占比"] - heat["昨日上涨占比"]).round(3)
        else:
            heat["昨日排名"] = None
            heat["排名变化"] = None
            heat["昨日热度分"] = None
            heat["热度变化"] = None
            heat["昨日成交额亿"] = None
            heat["成交额变化亿"] = None
            heat["中位涨幅变化"] = None
            heat["上涨占比变化"] = None
        top = heat.head(HOT_SECTOR_TOPN)
        strategic = heat[
            (heat["主题匹配"])
            & ((heat["中位涨幅"] > 0) | (heat["上涨占比"] >= 0.5))
        ].head(HOT_SECTOR_CANDIDATE_TOPN)
        hot = set(top["industry"]) | set(strategic["industry"])

    path = os.path.join(OUTPUT_DIR, f"sector_heat_{ts}.csv")
    heat.to_csv(path, index=False, encoding="utf-8-sig")
    return path, heat, hot


def _trend_metrics(kline: list[list[float]]) -> dict | None:
    """强趋势启动指标。只使用最新 K 线历史, 不依赖筹码密集。"""
    if not kline or len(kline) < 60:
        return None
    import numpy as np
    arr = np.array(kline, dtype=float)
    closes, highs, trs = arr[:, 0], arr[:, 1], arr[:, 3]
    cur = float(closes[-1])
    ma5 = float(np.mean(closes[-5:]))
    ma10 = float(np.mean(closes[-10:]))
    ma20 = float(np.mean(closes[-20:]))
    ma60 = float(np.mean(closes[-60:]))
    high20_prev = float(np.max(highs[-21:-1])) if len(highs) >= 21 else float(np.max(highs[-20:]))
    high20 = float(np.max(highs[-20:]))
    base_vol = float(np.mean(trs[-25:-5])) if len(trs) >= 25 else 0.0
    vol_ratio = float(np.mean(trs[-5:])) / base_vol if base_vol > 0 else None
    mom5 = (cur / closes[-6] - 1) * 100 if closes[-6] > 0 else None
    mom20 = (cur / closes[-21] - 1) * 100 if len(closes) >= 21 and closes[-21] > 0 else None
    near_high20 = cur / high20 if high20 > 0 else None
    return {
        "现价": round(cur, 2),
        "MA5": round(ma5, 2),
        "MA10": round(ma10, 2),
        "MA20": round(ma20, 2),
        "MA60": round(ma60, 2),
        "放量比": round(vol_ratio, 3) if vol_ratio is not None else None,
        "近5日涨幅": round(mom5, 2) if mom5 is not None else None,
        "近20日涨幅": round(mom20, 2) if mom20 is not None else None,
        "突破20日新高": bool(cur >= high20_prev),
        "接近20日高点": round(near_high20, 4) if near_high20 is not None else None,
        "均线多头": bool(ma5 > ma10 > ma20),
        "站上MA20": bool(cur > ma20),
    }


def _trend_tier(m: dict, turnover_ew: float | None, theme_hit: bool,
                hot_sector: bool) -> tuple[str, bool]:
    """返回 (A/B/C档, 是否过热)。"""
    mom5 = m.get("近5日涨幅") or 0
    mom20 = m.get("近20日涨幅") or 0
    near_high = m.get("接近20日高点") or 0
    vol_ratio = m.get("放量比") or 0
    overheat = bool(mom5 > 35 or mom20 > 100 or vol_ratio > 3)
    if overheat:
        return "C-过热观察", True
    if (theme_hit or hot_sector) and m.get("突破20日新高") and 8 <= mom5 <= 25 \
            and mom20 < 50 and (turnover_ew or 0) >= 20 and 1.0 <= vol_ratio <= 2.5:
        return "A-主线新高", False
    if (theme_hit or hot_sector) and m.get("站上MA20") and near_high >= 0.95 \
            and 5 <= mom5 <= 25 and mom20 < 60 and (turnover_ew or 0) >= 10:
        return "B-趋势确认", False
    return "C-观察", False


def _close_strength(kline: list[list[float]]) -> float | None:
    if not kline:
        return None
    close, high, low = float(kline[-1][0]), float(kline[-1][1]), float(kline[-1][2])
    if high <= low:
        return 1.0 if close >= high else None
    return round((close - low) / (high - low), 4)


def _push_tier(change_pct: float, main_pct: float, super_in: float,
               m: dict, close_strength: float) -> tuple[str, str]:
    """返回 (观察档位, 风险标签)。仅用于提示, 不作为买入建议。"""
    mom20 = m.get("近20日涨幅") or 0
    vol_ratio = m.get("放量比") or 0
    risk = "正常"
    if mom20 > 100:
        risk = "过热不追"
    elif mom20 >= 50 or change_pct >= 9.5 or vol_ratio > 3:
        risk = "高位接力"
    elif mom20 >= 30:
        risk = "中段"
    else:
        risk = "早段"

    if risk == "早段" and main_pct >= 8 and super_in > 0 and close_strength >= 0.75 \
            and m.get("站上MA20"):
        return "观察-早段推盘", risk
    if risk in ("早段", "中段") and main_pct >= 5 and close_strength >= 0.65:
        return "观察-推盘确认", risk
    if risk == "高位接力":
        return "观察-高位分歧", risk
    return "观察-过热不追", risk


def export_push_starts(uni_path: str, throttle: float,
                       hot_sectors: set[str] | None = None) -> tuple[str, list[dict]]:
    """导出推盘观察池。用于提示主力/超大单推价格痕迹, 不参与买入建议。"""
    df = pd.read_csv(uni_path, dtype={"code": str})
    df["code"] = df["code"].str.zfill(6)
    num_cols = (
        "price", "change_pct", "turnover_yuan", "volume_ratio", "pe_ttm",
        "main_net_inflow", "main_net_pct", "super_net_inflow",
        "super_net_pct", "large_net_inflow", "large_net_pct",
    )
    for col in num_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
    hot_sectors = hot_sectors or set()
    df["hot_sector"] = df.get("industry", "").astype(str).isin(hot_sectors)

    candidates = df[
        (df["turnover_yuan"].fillna(0) >= PUSH_TURNOVER_FLOOR)
        & (df["change_pct"].fillna(-999) >= PUSH_MIN_CHANGE)
        & (df["main_net_inflow"].fillna(0) > 0)
        & (df["main_net_pct"].fillna(-999) >= PUSH_MIN_MAIN_NET_PCT)
        & ((df["super_net_inflow"].fillna(0) > 0) | (df["large_net_inflow"].fillna(0) > 0))
        & (df["pe_ttm"].fillna(0) > 0)
    ].copy()
    if candidates.empty:
        recs: list[dict] = []
    else:
        candidates = candidates.sort_values(
            ["hot_sector", "main_net_pct", "main_net_inflow", "turnover_yuan"],
            ascending=[False, False, False, False],
        ).head(PUSH_SCAN_BUDGET)
        recs = []
        for _, r in candidates.iterrows():
            code = r["code"]
            kline = chip_calc.fetch_kline(code)
            m = _trend_metrics(kline) if kline else None
            close_strength = _close_strength(kline) if kline else None
            if not m or close_strength is None:
                continue
            stands_ma5 = m["现价"] > m["MA5"]
            if not stands_ma5 or close_strength < PUSH_MIN_CLOSE_STRENGTH:
                time.sleep(throttle)
                continue

            tier, risk = _push_tier(
                float(r["change_pct"]), float(r["main_net_pct"]),
                float(r.get("super_net_inflow") or 0), m, close_strength,
            )
            main_ew = round(float(r["main_net_inflow"]) / 1e8, 2)
            super_ew = round(float(r.get("super_net_inflow") or 0) / 1e8, 2)
            large_ew = round(float(r.get("large_net_inflow") or 0) / 1e8, 2)
            turnover_ew = round(float(r["turnover_yuan"]) / 1e8, 2)
            score = (
                float(r["main_net_pct"]) * 2
                + min(main_ew, 10) * 2
                + close_strength * 10
                + (5 if m.get("站上MA20") else 0)
                + (3 if r.get("hot_sector") else 0)
                - (12 if risk == "过热不追" else 0)
                - (5 if risk == "高位接力" else 0)
            )
            recs.append({
                "code": code,
                "name": r.get("name"),
                "industry": r.get("industry"),
                "现价": m["现价"],
                "当日涨幅": round(float(r["change_pct"]), 2),
                "近5日涨幅": m["近5日涨幅"],
                "近20日涨幅": m["近20日涨幅"],
                "放量比": m["放量比"],
                "收盘强度": close_strength,
                "站上MA5": stands_ma5,
                "站上MA20": m["站上MA20"],
                "主力净流入亿": main_ew,
                "主力净占比": round(float(r["main_net_pct"]), 2),
                "超大单净流入亿": super_ew,
                "大单净流入亿": large_ew,
                "成交额亿": turnover_ew,
                "量比": r.get("volume_ratio"),
                "热门板块": bool(r.get("hot_sector")),
                "推盘档位": tier,
                "风险分层": risk,
                "推盘分": round(score, 2),
            })
            time.sleep(throttle)

    risk_rank = {"早段": 3, "中段": 2, "高位接力": 1, "过热不追": 0}
    recs.sort(key=lambda x: (risk_rank.get(x["风险分层"], -1), x["推盘分"]), reverse=True)
    recs = recs[:PUSH_TOPN]
    ts = datetime.now().strftime("%Y%m%d")
    path = os.path.join(OUTPUT_DIR, f"push_pool_{ts}.csv")
    pd.DataFrame(recs).to_csv(path, index=False, encoding="utf-8-sig")
    return path, recs


def export_trend_starts(uni_path: str, throttle: float,
                        hot_sectors: set[str] | None = None) -> tuple[str, list[dict]]:
    """导出强趋势启动池, 捕捉兆易创新/德明利这类非横盘强趋势票。"""
    df = pd.read_csv(uni_path, dtype={"code": str})
    df["code"] = df["code"].str.zfill(6)
    for col in ("price", "change_60d_pct", "turnover_yuan", "volume_ratio", "pe_ttm"):
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    hot_sectors = hot_sectors or set()
    df["theme_hit"] = df.get("industry", "").astype(str).apply(
        lambda s: any(k in s for k in TREND_INDUSTRIES)
    )
    df["hot_sector"] = df.get("industry", "").astype(str).isin(hot_sectors)

    candidates = df[
        (df["change_60d_pct"].fillna(-999) >= TREND_MIN_60D)
        & (df["turnover_yuan"].fillna(0) >= TREND_TURNOVER_FLOOR)
        & (df["pe_ttm"].fillna(0) > 0)
        & (df["theme_hit"] | df["hot_sector"])
    ].copy()
    if candidates.empty:
        recs: list[dict] = []
    else:
        candidates = candidates.sort_values(
            ["hot_sector", "theme_hit", "turnover_yuan", "change_60d_pct"],
            ascending=[False, False, False, False],
        ).head(TREND_SCAN_BUDGET)

        recs = []
        for _, r in candidates.iterrows():
            code = r["code"]
            kline = chip_calc.fetch_kline(code)
            m = _trend_metrics(kline) if kline else None
            if not m:
                continue
            mom5 = m.get("近5日涨幅")
            near_high = m.get("接近20日高点")
            theme_hit = bool(r.get("theme_hit"))
            hot_sector = bool(r.get("hot_sector"))
            turnover_yuan = r.get("turnover_yuan")
            strong_breakout = (
                m["站上MA20"]
                and mom5 is not None and mom5 >= TREND_MIN_MOM5
                and near_high is not None and near_high >= TREND_NEAR_HIGH20
            )
            theme_anchor = (
                theme_hit
                and pd.notna(turnover_yuan)
                and turnover_yuan >= TREND_THEME_TURNOVER_FLOOR
                and m["站上MA20"]
                and mom5 is not None and mom5 >= 4.0
                and near_high is not None and near_high >= 0.90
            )
            if not (strong_breakout or theme_anchor):
                time.sleep(throttle)
                continue
            turnover_ew = round(turnover_yuan / 1e8, 2) if pd.notna(turnover_yuan) else None
            turnover_score = min(turnover_ew / 20, 10) if turnover_ew is not None else 0
            tier, overheat = _trend_tier(m, turnover_ew, theme_hit, hot_sector)
            overheat_penalty = 20 if overheat else 0
            score = (
                float(mom5)
                + max(float(m.get("近20日涨幅") or 0), 0) * 0.25
                + (8 if m["突破20日新高"] else 0)
                + (4 if m["均线多头"] else 0)
                + (12 if theme_hit else 0)
                + (8 if hot_sector else 0)
                + turnover_score
                + (math.log10(turnover_yuan) - 8 if pd.notna(turnover_yuan) and turnover_yuan > 0 else 0)
                - overheat_penalty
            )
            recs.append({
                "code": code,
                "name": r.get("name"),
                "industry": r.get("industry"),
                "现价": m["现价"],
                "60日涨幅": round(float(r.get("change_60d_pct")), 2),
                "近5日涨幅": m["近5日涨幅"],
                "近20日涨幅": m["近20日涨幅"],
                "放量比": m["放量比"],
                "站上MA20": m["站上MA20"],
                "均线多头": m["均线多头"],
                "突破20日新高": m["突破20日新高"],
                "接近20日高点": m["接近20日高点"],
                "成交额亿": turnover_ew,
                "量比": r.get("volume_ratio"),
                "PE": r.get("pe_ttm"),
                "入选原因": "强趋势突破" if strong_breakout else "主题大票异动",
                "主题大票": theme_anchor,
                "热门板块": hot_sector,
                "趋势档位": tier,
                "过热风险": "是" if overheat else "否",
                "趋势分": round(score, 2),
            })
            time.sleep(throttle)
    strong = [r for r in recs if r["入选原因"] == "强趋势突破"]
    anchors = [r for r in recs if r.get("主题大票")]
    tier_rank = {"B-趋势确认": 3, "A-主线新高": 2, "C-观察": 1, "C-过热观察": 0}
    strong.sort(key=lambda x: (tier_rank.get(x["趋势档位"], -1), x["趋势分"]), reverse=True)
    anchors.sort(key=lambda x: (x["成交额亿"] or 0, x["趋势分"]), reverse=True)
    dedup: dict[str, dict] = {}
    for r in strong[:20] + anchors[:10]:
        dedup.setdefault(r["code"], r)
    recs = list(dedup.values())
    recs.sort(key=lambda x: (
        -tier_rank.get(x["趋势档位"], -1),
        x["入选原因"] != "强趋势突破",
        -x["趋势分"],
    ))
    recs = recs[:TREND_TOPN]
    ts = datetime.now().strftime("%Y%m%d")
    path = os.path.join(OUTPUT_DIR, f"trend_pool_{ts}.csv")
    pd.DataFrame(recs).to_csv(path, index=False, encoding="utf-8-sig")
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

    heat_df = None
    try:
        heat_path, heat_df, hot_sectors = export_sector_heat(uni)
        top_sectors = heat_df.head(8).to_dict("records") if not heat_df.empty else []
        print(f"[output] 板块热度 → {heat_path}")
        if top_sectors:
            print("[sector] 热门板块: " + " / ".join(str(s["industry"]) for s in top_sectors))
        push_path, push_recs = export_push_starts(uni, throttle=throttle,
                                                  hot_sectors=hot_sectors)
        print(f"[output] 推盘观察池 {len(push_recs)} 只 → {push_path}")
        for i, r in enumerate(push_recs, 1):
            print(f"  P{i:>2}. {r['code']} {r['name']} {r.get('推盘档位')} "
                  f"主力={r['主力净流入亿']:+.2f}亿/{r['主力净占比']:+.1f}% "
                  f"强度={r['收盘强度']:.0%} 风险={r['风险分层']}")
        trend_path, trend_recs = export_trend_starts(uni, throttle=throttle,
                                                     hot_sectors=hot_sectors)
        print(f"[output] 强趋势启动池 {len(trend_recs)} 只 → {trend_path}")
        for i, r in enumerate(trend_recs, 1):
            print(f"  T{i:>2}. {r['code']} {r['name']} "
                  f"{r.get('趋势档位')} "
                  f"5日={r['近5日涨幅']:+.1f}% 20日={r['近20日涨幅']:+.1f}% "
                  f"近20高={r['接近20日高点']:.0%} 额={r['成交额亿']}亿")
    except Exception as e:  # noqa: BLE001
        trend_recs = []
        push_recs = []
        top_sectors = []
        print(f"[trend] 强趋势启动池失败 (不影响主流程): {e}")

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
            import sector_chart
            charts = {}
            for r in passed[:HIGH_TOPN]:           # 对入选标的画图
                cp = plot_chips.plot_one(r["code"], r["name"])
                if cp:
                    charts[r["code"]] = cp
            ov = overview.build_overview(passed[:HIGH_TOPN])   # 拼总览图
            sc_path = None
            if heat_df is not None and not heat_df.empty:
                sc_path = sector_chart.build_sector_chart(heat_df)   # 板块热度图
            notify.send_daily(recs, passed, charts, overview_path=ov,
                              trend_recs=trend_recs, hot_sectors=top_sectors,
                              push_recs=push_recs, sector_chart_path=sc_path)
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
