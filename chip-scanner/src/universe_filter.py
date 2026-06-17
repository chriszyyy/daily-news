"""全市场快照抓取 + 基础硬过滤 (冰封池入口)。

复用仓库现有抓取器 tools/scanner/fetch_eastmoney.py (东财 push2, 节流+UA轮换+退避),
字段含: price/turnover_yuan/turnover_rate_pct/volume_ratio/market_cap/
float_market_cap/list_date/change_60d_pct/change_ytd_pct/pb/industry/
main_net_inflow/main_net_pct/super_net_inflow/large_net_inflow。

硬过滤 (剔除):
  1. 板块资格   — 排除科创(688/689)/创业(300/301)/北交所(4/8/9)
  2. ST/退市    — 名称含 ST / 退
  3. 高价股     — 收盘价 > 1000
  4. 停牌/无量  — 价格 0 或 成交额 0
  5. 流动性     — 日成交额 < 5000 万 (及格线)
  6. 次新股     — 上市 < 365 天 (无历史套牢盘, 不可能形成低位单峰)

标记列 (不剔除, 供下游观察池参考):
  - 成交额占流通比%  — 健康度 1.5%~3%
  - 健康度标签       — 健康/偏低缩量/偏高活跃
  - 高位标记         — 60日涨幅过高 (位置判断, 不硬砍)
  - 量比异动标记     — 量比过高

注: 按用户要求, 流通市值不设区间 (宁可多看, 跑慢点)。
"""

from __future__ import annotations

import os
import sys
from datetime import datetime

import pandas as pd

# 复用仓库现有抓取器
_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
sys.path.insert(0, os.path.join(_REPO_ROOT, "tools", "scanner"))
import fetch_eastmoney as emf  # noqa: E402

# ---- 过滤阈值 (集中配置) ----
PRICE_CAP = 1000.0            # 收盘价上限 (元)
TURNOVER_FLOOR = 5000e4       # 日成交额下限 5000 万 (元)
EXCLUDE_PREFIXES = ("688", "689", "300", "301", "4", "8", "9")  # 科创/创业/北交所
ST_FLAGS = ("ST", "退")       # *ST 已被 ST 子串覆盖
NEW_STOCK_DAYS = 365          # 次新股门槛 (天)
HEALTHY_RATIO_LO, HEALTHY_RATIO_HI = 1.5, 3.0   # 成交额/流通市值 健康区间 %
HIGH_RUN_60D = 80.0           # 60 日涨幅高位标记线 %
VOL_RATIO_SPIKE = 5.0         # 量比异动线

OUTPUT_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "output")
SLEEP_SEC = 4.0               # 页间节流


def fetch_spot() -> pd.DataFrame:
    rows, meta = emf.fetch_all(sleep_sec=SLEEP_SEC, verbose=True)
    print(f"[fetch] meta={meta}")
    df = pd.DataFrame(rows)
    df["code"] = df["code"].astype(str).str.zfill(6)
    return df


def apply_basic_filter(df: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    stats: dict[str, int] = {"原始": len(df)}
    w = df.copy()

    # 1. 板块资格
    w = w[~w["code"].str.startswith(EXCLUDE_PREFIXES)]
    stats["排除科创创业北交所后"] = len(w)

    # 2. ST / 退市
    name = w["name"].astype(str)
    w = w[~name.str.contains("|".join(ST_FLAGS), regex=True, na=False)]
    stats["排除ST退市后"] = len(w)

    # 3. 高价股
    w["price"] = pd.to_numeric(w["price"], errors="coerce")
    w = w[w["price"].notna() & (w["price"] <= PRICE_CAP)]
    stats["排除高价股后"] = len(w)

    # 4. 停牌/无量 (先于流动性, 避免 0 干扰)
    w["turnover_yuan"] = pd.to_numeric(w["turnover_yuan"], errors="coerce")
    w = w[(w["price"] > 0) & (w["turnover_yuan"] > 0)]
    stats["排除停牌无量后"] = len(w)

    # 5. 流动性及格线
    w = w[w["turnover_yuan"] >= TURNOVER_FLOOR]
    stats["流动性及格后"] = len(w)

    # 6. 次新股
    ld = pd.to_datetime(w["list_date"].astype("Int64").astype(str),
                        format="%Y%m%d", errors="coerce")
    age_days = (pd.Timestamp.now() - ld).dt.days
    w = w[age_days.notna() & (age_days >= NEW_STOCK_DAYS)]
    stats["排除次新股后"] = len(w)

    # 7. 剔除亏损公司 (PE_ttm <= 0; NaN 保留, 由下游 PE>0 再卡)
    w["pe_ttm"] = pd.to_numeric(w["pe_ttm"], errors="coerce")
    w = w[~(w["pe_ttm"].notna() & (w["pe_ttm"] <= 0))]
    stats["排除亏损后"] = len(w)

    # ---- 标记列 (不剔除) ----
    w["float_market_cap"] = pd.to_numeric(w["float_market_cap"], errors="coerce")
    w["成交额占流通比%"] = (w["turnover_yuan"] / w["float_market_cap"] * 100).round(2)

    def _health(r) -> str:
        if pd.isna(r):
            return "未知"
        if r < HEALTHY_RATIO_LO:
            return "偏低/缩量"
        if r > HEALTHY_RATIO_HI:
            return "偏高/活跃"
        return "健康"

    w["健康度"] = w["成交额占流通比%"].apply(_health)
    w["change_60d_pct"] = pd.to_numeric(w["change_60d_pct"], errors="coerce")
    w["高位标记"] = w["change_60d_pct"] > HIGH_RUN_60D
    w["volume_ratio"] = pd.to_numeric(w["volume_ratio"], errors="coerce")
    w["量比异动"] = w["volume_ratio"] > VOL_RATIO_SPIKE

    return w, stats


def main() -> None:
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    raw = fetch_spot()
    filtered, stats = apply_basic_filter(raw)

    print("\n==== 过滤漏斗 ====")
    for k, v in stats.items():
        print(f"  {k:<18}: {v}")
    print(f"  健康度分布        : {filtered['健康度'].value_counts().to_dict()}")
    print(f"  高位标记数        : {int(filtered['高位标记'].sum())}")

    ts = datetime.now().strftime("%Y%m%d")
    out_path = os.path.join(OUTPUT_DIR, f"universe_{ts}.csv")
    cols = ["code", "name", "price", "change_pct", "change_60d_pct",
            "turnover_yuan", "float_market_cap", "turnover_rate_pct",
            "volume_ratio", "pe_ttm", "成交额占流通比%", "健康度", "高位标记",
            "量比异动", "main_net_inflow", "main_net_pct",
            "super_net_inflow", "super_net_pct", "large_net_inflow",
            "large_net_pct", "industry"]
    cols = [c for c in cols if c in filtered.columns]
    filtered[cols].to_csv(out_path, index=False, encoding="utf-8-sig")
    print(f"\n[output] {len(filtered)} 只 → {out_path}")


if __name__ == "__main__":
    main()
