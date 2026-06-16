"""筹码分布 — 自实现弹性 K 线抓取 + 纯 Python 三角分布算法。

替代 akshare.stock_cyq_em (其依赖 py_mini_racer 本地 JS, 慢且单 host 易限流)。

算法 (业界通用三角分布衰减模型):
  对每个历史交易日, 当日成交筹码按三角分布散布在 [最低, 最高] 区间
  (峰值在均价); 历史筹码按当日换手率衰减, 新筹码按换手率注入。
  迭代得到 价格→筹码量 分布, 再求:
    获利比例 = 现价以下筹码 / 总筹码
    平均成本 = 加权均价
    90成本低/高 = 中央 90% 筹码的价格区间
    SCR (90集中度) = (高 - 低) / (高 + 低)
"""

from __future__ import annotations

import random
import time
from datetime import date

import numpy as np
import requests

# 主源: 腾讯 (proxy.finance.qq.com, 含换手率, 未被封)
TX_URL = "https://proxy.finance.qq.com/ifzqgtimg/appstock/app/newfqkline/get"
# 备用源: 东财 (push2his, 高频易被封 IP)
EM_HOSTS = [
    "https://push2his.eastmoney.com",
    "https://48.push2his.eastmoney.com",
    "https://76.push2his.eastmoney.com",
]
UA = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/121.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:120.0) Gecko/20100101 Firefox/120.0",
]

KLINE_DAYS = 120        # 取近 120 交易日构建筹码 (聚焦近期密集峰; 250日会稀释)
GRID = 1500             # 价格网格精细度
DECAY = 1.0             # 换手衰减系数 (1.0 = 标准)
DOM_HALF_FRAC = 0.06    # 主峰占比统计带宽: 主峰 ±6% 价格内的筹码占比
SHARP_HALF_FRAC = 0.02  # 尖锐度统计带宽: 主峰 ±2% 价格内的筹码占比 (越高越尖)
# 单峰判据 (次峰检测) 参数
PEAK_SMOOTH_FRAC = 0.08  # 峰检测平滑窗口 (占网格比例)
PEAK_GAP_FRAC = 0.10     # 峰间最小间距 (占网格比例, 合并相邻毛刺)


def _second_peak_ratio(chips: np.ndarray) -> float:
    """次峰/主峰 高度比 (0=纯单峰, 接近1=真双峰)。用于判定是否单峰。"""
    n = len(chips)
    w = max(int(n * PEAK_SMOOTH_FRAC), 5)
    ys = np.convolve(chips, np.ones(w) / w, mode="same")
    gap = max(int(n * PEAK_GAP_FRAC), 1)
    idx = [i for i in range(1, n - 1) if ys[i] > ys[i - 1] and ys[i] >= ys[i + 1]]
    idx.sort(key=lambda i: ys[i], reverse=True)
    kept: list[int] = []
    for i in idx:
        if all(abs(i - j) >= gap for j in kept):
            kept.append(i)
    if len(kept) < 2 or ys[kept[0]] <= 0:
        return 0.0
    return float(ys[kept[1]] / ys[kept[0]])


def _secid(code: str) -> str:
    return f"{'1' if code.startswith('6') else '0'}.{code}"


def _tx_symbol(code: str) -> str:
    return f"{'sh' if code.startswith('6') else 'sz'}{code}"


def fetch_kline_tx(code: str, lmt: int = KLINE_DAYS,
                   max_retries: int = 2) -> list[list[float]] | None:
    """腾讯日 K (主源)。返回 [[close,high,low,turnover_rate],...] 旧→新。

    腾讯日 K 行: [日期,开,收,高,低,量(手),{},换手率%,额(万),...]
    """
    sym = _tx_symbol(code)
    today = date.today()
    start = today.replace(year=today.year - 2).isoformat()  # 回溯足够远, 由 lmt 截断
    end = "2050-12-31"
    params = {"param": f"{sym},day,{start},{end},{lmt},"}
    for attempt in range(max_retries):
        try:
            r = requests.get(TX_URL, params=params,
                             headers={"User-Agent": random.choice(UA)},
                             timeout=8)
            r.raise_for_status()
            node = (r.json().get("data") or {}).get(sym) or {}
            rows = node.get("day") or node.get("qfqday")
            if not rows:
                return None
            out = []
            for p in rows:
                # close=p[2], high=p[3], low=p[4], turnover_rate%=p[7]
                try:
                    tr = float(p[7]) if len(p) > 7 and p[7] not in ("", None) else 0.0
                except (ValueError, TypeError):
                    tr = 0.0
                out.append([float(p[2]), float(p[3]), float(p[4]), tr])
            return out
        except Exception:  # noqa: BLE001
            time.sleep(0.5)
    return None


def fetch_kline_em(code: str, lmt: int = KLINE_DAYS,
                   max_retries: int = 2) -> list[list[float]] | None:
    """东财日 K (备用源)。返回 [[close,high,low,turnover_rate],...] 旧→新。"""
    params = {
        "secid": _secid(code), "fields1": "f1,f2,f3",
        "fields2": "f51,f52,f53,f54,f55,f56,f57,f61",
        "klt": "101", "fqt": "0", "end": "20500101", "lmt": str(lmt),
    }
    for attempt in range(max_retries):
        host = EM_HOSTS[attempt % len(EM_HOSTS)]
        try:
            r = requests.get(f"{host}/api/qt/stock/kline/get", params=params,
                             headers={"User-Agent": random.choice(UA),
                                      "Referer": "https://quote.eastmoney.com/"},
                             timeout=8)
            r.raise_for_status()
            klines = (r.json().get("data") or {}).get("klines")
            if not klines:
                return None
            out = []
            for line in klines:
                p = line.split(",")
                # date,open,close,high,low,vol,amount,turnover_rate
                close, high, low, tr = (float(p[2]), float(p[3]),
                                        float(p[4]), float(p[7]))
                out.append([close, high, low, tr])
            return out
        except Exception:  # noqa: BLE001
            time.sleep(0.5)
    return None


def fetch_kline(code: str, lmt: int = KLINE_DAYS) -> list[list[float]] | None:
    """弹性抓取: 腾讯优先, 失败回退东财。"""
    out = fetch_kline_tx(code, lmt)
    if out:
        return out
    return fetch_kline_em(code, lmt)


def compute_chips(kline: list[list[float]]) -> dict | None:
    """三角分布衰减算法, 返回筹码指标。"""
    if not kline or len(kline) < 20:
        return None
    arr = np.array(kline, dtype=float)
    closes, highs, lows, trs = arr[:, 0], arr[:, 1], arr[:, 2], arr[:, 3]

    pmin, pmax = lows.min(), highs.max()
    if pmax <= pmin:
        return None
    grid = np.linspace(pmin, pmax, GRID)
    chips = np.zeros(GRID)

    for close, high, low, tr in zip(closes, highs, lows, trs):
        if high <= low:
            high = low + 0.01
        avg = (high + low + close) / 3.0
        # 三角分布密度 (峰值在 avg)
        dens = np.zeros(GRID)
        mask_lo = (grid >= low) & (grid <= avg)
        mask_hi = (grid > avg) & (grid <= high)
        if avg > low:
            dens[mask_lo] = (grid[mask_lo] - low) / (avg - low)
        if high > avg:
            dens[mask_hi] = (high - grid[mask_hi]) / (high - avg)
        s = dens.sum()
        if s == 0:
            continue
        dens /= s
        turnover = min(max(tr / 100.0 * DECAY, 0.0), 1.0)
        chips = chips * (1 - turnover) + dens * turnover

    total = chips.sum()
    if total <= 0:
        return None
    chips /= total

    cur = closes[-1]
    profit_ratio = float(chips[grid < cur].sum())
    avg_cost = float((grid * chips).sum())
    cdf = np.cumsum(chips)
    lo90 = float(grid[np.searchsorted(cdf, 0.05)])
    hi90 = float(grid[min(np.searchsorted(cdf, 0.95), GRID - 1)])
    scr = (hi90 - lo90) / (hi90 + lo90) if (hi90 + lo90) > 0 else None

    # 70% 集中度 (核心: 主峰密集度, 剔除两端长尾散筹)
    lo70 = float(grid[np.searchsorted(cdf, 0.15)])
    hi70 = float(grid[min(np.searchsorted(cdf, 0.85), GRID - 1)])
    scr70 = (hi70 - lo70) / (hi70 + lo70) if (hi70 + lo70) > 0 else None
    # 主峰带宽相对现价 (70%筹码挤在 ±band70/2 内)
    band70 = (hi70 - lo70) / cur if cur > 0 else None

    # 主峰占比: 主峰 ±DOM_HALF 价格带内的筹码占比 (越高越像单一尖峰)
    peak_idx = int(np.argmax(chips))
    peak_price = float(grid[peak_idx])
    dom_half = peak_price * DOM_HALF_FRAC
    dom_mask = (grid >= peak_price - dom_half) & (grid <= peak_price + dom_half)
    dominance = float(chips[dom_mask].sum())
    # 尖锐度: 主峰 ±SHARP_HALF 内筹码占比 (越高越尖)
    sharp_half = peak_price * SHARP_HALF_FRAC
    sharp_mask = (grid >= peak_price - sharp_half) & (grid <= peak_price + sharp_half)
    sharpness = float(chips[sharp_mask].sum())
    # 现价相对主峰 (带符号): >0 现价在主峰上方(突破/启动), <0 在下方(套牢压顶)
    pos_vs_peak = (cur - peak_price) / peak_price if peak_price > 0 else None
    # 次峰/主峰高度比 (单峰判据): 0=纯单峰, 接近1=真双峰
    second_ratio = _second_peak_ratio(chips)

    return {
        "现价": round(cur, 2),
        "获利比例": round(profit_ratio, 4),
        "平均成本": round(avg_cost, 2),
        "90成本低": round(lo90, 2),
        "90成本高": round(hi90, 2),
        "SCR": round(scr, 4) if scr is not None else None,
        "70成本低": round(lo70, 2),
        "70成本高": round(hi70, 2),
        "SCR70": round(scr70, 4) if scr70 is not None else None,
        "带宽70": round(band70, 4) if band70 is not None else None,
        "主峰价": round(peak_price, 2),
        "主峰占比": round(dominance, 4),
        "尖锐度": round(sharpness, 4),
        "距主峰": round(pos_vs_peak, 4) if pos_vs_peak is not None else None,
        "次峰比": round(second_ratio, 4),
    }


def compute_distribution(kline: list[list[float]]) -> tuple | None:
    """返回 (grid, chips, 指标dict) 用于绘制筹码分布图。"""
    if not kline or len(kline) < 20:
        return None
    m = compute_chips(kline)
    if m is None:
        return None
    arr = np.array(kline, dtype=float)
    closes, highs, lows, trs = arr[:, 0], arr[:, 1], arr[:, 2], arr[:, 3]
    pmin, pmax = lows.min(), highs.max()
    grid = np.linspace(pmin, pmax, GRID)
    chips = np.zeros(GRID)
    for close, high, low, tr in zip(closes, highs, lows, trs):
        if high <= low:
            high = low + 0.01
        avg = (high + low + close) / 3.0
        dens = np.zeros(GRID)
        mask_lo = (grid >= low) & (grid <= avg)
        mask_hi = (grid > avg) & (grid <= high)
        if avg > low:
            dens[mask_lo] = (grid[mask_lo] - low) / (avg - low)
        if high > avg:
            dens[mask_hi] = (high - grid[mask_hi]) / (high - avg)
        s = dens.sum()
        if s == 0:
            continue
        dens /= s
        turnover = min(max(tr / 100.0 * DECAY, 0.0), 1.0)
        chips = chips * (1 - turnover) + dens * turnover
    total = chips.sum()
    if total > 0:
        chips /= total
    return grid, chips, m


def fetch_chip_latest(code: str) -> dict | None:
    kline = fetch_kline(code)
    if kline is None:
        return None
    m = compute_chips(kline)
    if m is None:
        return None
    m["code"] = code
    return m


if __name__ == "__main__":
    import json
    print(json.dumps(fetch_chip_latest("600000"), ensure_ascii=False, indent=2))
