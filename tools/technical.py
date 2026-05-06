"""
技术指标计算工具库
用法: python tools/technical.py <数据文件.json> [--all | --ticker TICKER]

数据文件格式: data/prices/ 下的 JSON 文件，由 save_prices.py 生成。
输出: 每只股票的 MA20/MA60, RSI14, MACD, 布林带, 以及综合入场评分。
"""
import json
import sys
import os
from datetime import datetime


# ─── 核心计算函数 ───────────────────────────────────────────────

def calc_ma(closes: list[float], period: int) -> float | None:
    """简单移动平均线"""
    if len(closes) < period:
        return None
    return sum(closes[-period:]) / period


def calc_rsi(closes: list[float], period: int = 14) -> float | None:
    """相对强弱指标 (Wilder RSI)"""
    if len(closes) < period + 1:
        return None
    gains, losses = [], []
    for i in range(len(closes) - period, len(closes)):
        diff = closes[i] - closes[i - 1]
        gains.append(max(diff, 0))
        losses.append(max(-diff, 0))
    avg_gain = sum(gains) / period
    avg_loss = sum(losses) / period
    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    return 100 - 100 / (1 + rs)


def calc_macd(closes: list[float], fast: int = 12, slow: int = 26, signal: int = 9):
    """
    MACD 指标
    返回: (dif, dea, macd_bar, dif_history)
    - dif: 快线 - 慢线 (最新值)
    - dea: 信号线 (最新值)
    - macd_bar: 2 * (dif - dea)，红柱为正绿柱为负
    - dif_history: 全部 DIF 历史序列
    """
    if len(closes) < slow + signal:
        return None, None, None, []

    k_fast = 2 / (fast + 1)
    k_slow = 2 / (slow + 1)
    k_signal = 2 / (signal + 1)

    ema_fast = closes[0]
    ema_slow = closes[0]
    dif_history = []

    for c in closes[1:]:
        ema_fast = c * k_fast + ema_fast * (1 - k_fast)
        ema_slow = c * k_slow + ema_slow * (1 - k_slow)
        dif_history.append(ema_fast - ema_slow)

    # DEA = signal-period EMA of DIF
    if len(dif_history) < signal:
        return dif_history[-1] if dif_history else None, None, None, dif_history

    dea = dif_history[-signal * 3]  # 用更早的起点提高精度
    for d in dif_history[-signal * 3 + 1:]:
        dea = d * k_signal + dea * (1 - k_signal)

    dif = dif_history[-1]
    macd_bar = 2 * (dif - dea)
    return dif, dea, macd_bar, dif_history


def calc_bollinger(closes: list[float], period: int = 20, num_std: float = 2.0):
    """
    布林带
    返回: (upper, middle, lower, percent_b)
    - percent_b: 0-100, 当前价在带内的位置百分比
    """
    if len(closes) < period:
        return None, None, None, None
    data = closes[-period:]
    middle = sum(data) / period
    std = (sum((x - middle) ** 2 for x in data) / period) ** 0.5
    upper = middle + num_std * std
    lower = middle - num_std * std
    width = upper - lower
    percent_b = ((closes[-1] - lower) / width * 100) if width > 0 else 50.0
    return upper, middle, lower, percent_b


def calc_atr(highs: list[float], lows: list[float], closes: list[float], period: int = 14) -> float | None:
    """
    平均真实波幅 (ATR)
    用于评估波动性，辅助设定止损距离。
    """
    if len(closes) < period + 1:
        return None
    trs = []
    for i in range(len(closes) - period, len(closes)):
        tr = max(
            highs[i] - lows[i],
            abs(highs[i] - closes[i - 1]),
            abs(lows[i] - closes[i - 1])
        )
        trs.append(tr)
    return sum(trs) / period


def calc_volume_ma(volumes: list[float], period: int = 20) -> float | None:
    """成交量均线"""
    if len(volumes) < period:
        return None
    return sum(volumes[-period:]) / period


# ─── 综合分析 ──────────────────────────────────────────────────

def analyze_stock(ticker: str, dates: list[str], closes: list[float],
                  highs: list[float] = None, lows: list[float] = None,
                  volumes: list[float] = None) -> dict:
    """
    对单只股票计算全部技术指标，返回结构化结果。
    """
    last = closes[-1]
    ma20 = calc_ma(closes, 20)
    ma60 = calc_ma(closes, 60)
    rsi = calc_rsi(closes, 14)
    dif, dea, macd_bar, _ = calc_macd(closes)
    bb_upper, bb_mid, bb_lower, bb_pct = calc_bollinger(closes)

    atr = None
    if highs and lows:
        atr = calc_atr(highs, lows, closes, 14)

    vol_ma = None
    vol_ratio = None
    if volumes:
        vol_ma = calc_volume_ma(volumes, 20)
        if vol_ma and vol_ma > 0:
            vol_ratio = volumes[-1] / vol_ma

    # 趋势判定
    trend = "neutral"
    if ma20 and ma60:
        if last > ma20 > ma60:
            trend = "bullish"
        elif last < ma20 < ma60:
            trend = "bearish"
        elif last > ma20 and ma20 < ma60:
            trend = "recovering"
        elif last < ma20 and ma20 > ma60:
            trend = "weakening"

    # MA 交叉
    ma_cross = None
    if ma20 and ma60:
        ma_cross = "golden" if ma20 > ma60 else "death"

    # 入场评分 (1-5星)
    score = 3  # 基准中性
    reasons = []

    if rsi is not None:
        if rsi > 70:
            score -= 1
            reasons.append(f"RSI={rsi:.0f} overbought")
        elif rsi < 30:
            score += 1
            reasons.append(f"RSI={rsi:.0f} oversold opportunity")

    if ma_cross == "golden":
        score += 0.5
        reasons.append("MA golden cross")
    elif ma_cross == "death":
        score -= 0.5
        reasons.append("MA death cross")

    if ma20 and last > ma20:
        score += 0.5
        reasons.append("above MA20")
    elif ma20 and last < ma20:
        score -= 0.5
        reasons.append("below MA20")

    if macd_bar is not None:
        if macd_bar > 0:
            score += 0.5
            reasons.append("MACD bullish")
        else:
            score -= 0.5
            reasons.append("MACD bearish")

    if bb_pct is not None:
        if bb_pct < 15:
            score += 0.5
            reasons.append(f"BB%B={bb_pct:.0f}% near lower band")
        elif bb_pct > 85:
            score -= 0.5
            reasons.append(f"BB%B={bb_pct:.0f}% near upper band")

    score = max(1, min(5, round(score)))
    stars = "★" * score + "☆" * (5 - score)

    return {
        "ticker": ticker,
        "last_price": last,
        "last_date": dates[-1] if dates else None,
        "data_points": len(closes),
        "ma20": ma20,
        "ma60": ma60,
        "ma_cross": ma_cross,
        "rsi14": rsi,
        "macd_dif": dif,
        "macd_dea": dea,
        "macd_bar": macd_bar,
        "bb_upper": bb_upper,
        "bb_mid": bb_mid,
        "bb_lower": bb_lower,
        "bb_pct": bb_pct,
        "atr14": atr,
        "vol_ma20": vol_ma,
        "vol_ratio": vol_ratio,
        "trend": trend,
        "score": score,
        "stars": stars,
        "reasons": reasons,
    }


def format_report(result: dict) -> str:
    """将分析结果格式化为可读文本"""
    r = result
    lines = []
    lines.append(f"{'=' * 55}")
    lines.append(f"  {r['ticker']}  Last: {r['last_price']:.2f}  ({r['last_date']})")
    lines.append(f"  Data: {r['data_points']} points | Trend: {r['trend']} | Score: {r['stars']}")
    lines.append(f"{'=' * 55}")

    # MA
    ma20_str = f"{r['ma20']:.2f}" if r['ma20'] else "N/A"
    ma60_str = f"{r['ma60']:.2f}" if r['ma60'] else "N/A"
    ma20_pos = ""
    if r['ma20']:
        ma20_pos = " (above)" if r['last_price'] > r['ma20'] else " (BELOW)"
    ma60_pos = ""
    if r['ma60']:
        ma60_pos = " (above)" if r['last_price'] > r['ma60'] else " (BELOW)"
    lines.append(f"  MA20: {ma20_str}{ma20_pos}  MA60: {ma60_str}{ma60_pos}")
    if r['ma_cross']:
        lines.append(f"  MA Cross: {r['ma_cross']}")

    # RSI
    if r['rsi14'] is not None:
        rsi_note = "OVERBOUGHT" if r['rsi14'] > 70 else "OVERSOLD" if r['rsi14'] < 30 else "neutral"
        lines.append(f"  RSI14: {r['rsi14']:.1f} [{rsi_note}]")

    # MACD
    if r['macd_bar'] is not None:
        macd_note = "bullish" if r['macd_bar'] > 0 else "bearish"
        lines.append(f"  MACD: DIF={r['macd_dif']:.3f} DEA={r['macd_dea']:.3f} Bar={r['macd_bar']:.3f} [{macd_note}]")

    # BB
    if r['bb_pct'] is not None:
        bb_note = "near upper" if r['bb_pct'] > 80 else "near lower" if r['bb_pct'] < 20 else "middle"
        lines.append(f"  BB: U={r['bb_upper']:.2f} M={r['bb_mid']:.2f} L={r['bb_lower']:.2f} %B={r['bb_pct']:.0f}% [{bb_note}]")

    # ATR
    if r['atr14'] is not None:
        lines.append(f"  ATR14: {r['atr14']:.3f} (daily volatility)")

    # Volume
    if r['vol_ratio'] is not None:
        vol_note = "above avg" if r['vol_ratio'] > 1.2 else "below avg" if r['vol_ratio'] < 0.8 else "normal"
        lines.append(f"  Vol Ratio: {r['vol_ratio']:.2f}x [{vol_note}]")

    # Score reasons
    if r['reasons']:
        lines.append(f"  Entry signals: {', '.join(r['reasons'])}")

    lines.append("")
    return "\n".join(lines)


# ─── 数据加载 ──────────────────────────────────────────────────

def load_price_file(filepath: str) -> dict:
    """
    加载 data/prices/ 下的 JSON 价格文件。
    文件格式见 save_prices.py 的输出。
    """
    with open(filepath, 'r', encoding='utf-8') as f:
        return json.load(f)


# ─── CLI 入口 ──────────────────────────────────────────────────

def main():
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    if len(sys.argv) < 2:
        print("Usage: python tools/technical.py <price_file.json> [--ticker TICKER]")
        print("       python tools/technical.py data/prices/2026-05-01.json")
        print("       python tools/technical.py data/prices/2026-05-01.json --ticker 600667.SS")
        sys.exit(1)

    filepath = sys.argv[1]
    filter_ticker = None
    if "--ticker" in sys.argv:
        idx = sys.argv.index("--ticker")
        if idx + 1 < len(sys.argv):
            filter_ticker = sys.argv[idx + 1]

    data = load_price_file(filepath)
    meta = data.get("metadata", {})
    print(f"Data file: {filepath}")
    print(f"Generated: {meta.get('generated_at', 'unknown')}")
    print(f"Period: {meta.get('period', 'unknown')}")
    print()

    stocks = data.get("stocks", {})
    results = []

    for ticker, stock_data in stocks.items():
        if filter_ticker and ticker != filter_ticker:
            continue

        closes = [d["close"] for d in stock_data["data"]]
        highs = [d.get("high", d["close"]) for d in stock_data["data"]]
        lows = [d.get("low", d["close"]) for d in stock_data["data"]]
        volumes = [d.get("volume", 0) for d in stock_data["data"]]
        dates = [d["date"] for d in stock_data["data"]]

        result = analyze_stock(ticker, dates, closes, highs, lows, volumes)
        result["name"] = stock_data.get("name", ticker)
        results.append(result)
        print(format_report(result))

    # 汇总表
    if len(results) > 1:
        print("=" * 55)
        print("  SUMMARY")
        print("=" * 55)
        print(f"  {'Ticker':<16} {'Last':>8} {'RSI':>6} {'MACD':>8} {'BB%B':>6} {'Score'}")
        for r in sorted(results, key=lambda x: x['score'], reverse=True):
            rsi_str = f"{r['rsi14']:.0f}" if r['rsi14'] else "N/A"
            macd_str = f"{r['macd_bar']:.3f}" if r['macd_bar'] is not None else "N/A"
            bb_str = f"{r['bb_pct']:.0f}%" if r['bb_pct'] is not None else "N/A"
            print(f"  {r['ticker']:<16} {r['last_price']:>8.2f} {rsi_str:>6} {macd_str:>8} {bb_str:>6} {r['stars']}")
        print()


if __name__ == "__main__":
    main()
