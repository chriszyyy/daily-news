"""High 池标的的基本面增强 — 补充业绩(净利润/营收同比)+ 量价(量比/成交额)。

- 量价: 从最新 universe CSV 取 (volume_ratio / turnover_yuan), 无额外请求。
- 业绩: 同花顺财务摘要最新一期 (净利润同比 / 营收同比 / ROE), 逐只补 (≤20只, 快)。
"""

from __future__ import annotations

import os

import akshare as ak
import pandas as pd

OUTPUT_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "output")


def latest_universe() -> str:
    files = sorted(f for f in os.listdir(OUTPUT_DIR)
                   if f.startswith("universe_") and f.endswith(".csv"))
    return os.path.join(OUTPUT_DIR, files[-1]) if files else ""


def load_volume_map() -> dict:
    """code -> {量比, 成交额}。来自全市场快照, 无额外请求。"""
    path = latest_universe()
    if not path:
        return {}
    df = pd.read_csv(path, dtype={"code": str})
    df["code"] = df["code"].str.zfill(6)
    out = {}
    for _, r in df.iterrows():
        out[r["code"]] = {
            "量比": r.get("volume_ratio"),
            "成交额": r.get("turnover_yuan"),
            "换手率": r.get("turnover_rate_pct"),
        }
    return out


def _pct(v) -> float | None:
    """'34.83%' -> 34.83; False/NaN -> None。"""
    if v is None or v is False:
        return None
    try:
        s = str(v).replace("%", "").strip()
        return round(float(s), 1)
    except (ValueError, TypeError):
        return None


def fetch_earnings(code: str) -> dict:
    """同花顺财务摘要最新一期: 净利润同比 / 营收同比 / ROE。"""
    try:
        df = ak.stock_financial_abstract_ths(symbol=code, indicator="按报告期")
        if df is None or df.empty:
            return {}
        last = df.iloc[-1]
        return {
            "报告期": str(last.get("报告期", "")),
            "净利润同比": _pct(last.get("净利润同比增长率")),
            "营收同比": _pct(last.get("营业总收入同比增长率")),
            "ROE": _pct(last.get("净资产收益率")),
        }
    except Exception:  # noqa: BLE001
        return {}


def enrich(recs: list[dict]) -> list[dict]:
    """对 High 池记录补充量价 + 业绩。原地添加字段并返回。"""
    vmap = load_volume_map()
    for r in recs:
        code = r["code"]
        v = vmap.get(code, {})
        r["量比"] = v.get("量比")
        r["成交额亿"] = round(v["成交额"] / 1e8, 2) if v.get("成交额") else None
        e = fetch_earnings(code)
        r["净利润同比"] = e.get("净利润同比")
        r["营收同比"] = e.get("营收同比")
        r["ROE"] = e.get("ROE")
        r["报告期"] = e.get("报告期", "")
    return recs
