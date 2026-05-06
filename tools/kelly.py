"""
Kelly公式与仓位管理计算工具
用法: python tools/kelly.py

提供函数供 Claude 在 session 中计算:
- Kelly比例
- 半Kelly仓位金额
- 赔率计算
- 批量标的Kelly排序
"""
import json
import sys


def calc_odds(current: float, target: float, stop_loss: float) -> float:
    """
    计算赔率 (odds ratio)
    b = (target - current) / (current - stop_loss)
    """
    downside = current - stop_loss
    if downside <= 0:
        return float('inf')  # 止损在当前价之上，不合理
    return (target - current) / downside


def calc_kelly(odds: float, win_rate: float) -> float:
    """
    Kelly公式
    f* = (p * b - q) / b
    其中 p=胜率, q=1-p, b=赔率
    """
    q = 1 - win_rate
    return (win_rate * odds - q) / odds


def calc_position(kelly: float, total_capital: float, half: bool = True) -> float:
    """
    计算仓位金额
    half=True 使用半Kelly（实战推荐）
    """
    f = kelly / 2 if half else kelly
    if f <= 0:
        return 0
    return round(total_capital * f)


def analyze_candidates(candidates: list[dict], total_capital: float = 30000) -> list[dict]:
    """
    批量分析候选标的的Kelly仓位。

    candidates: [
        {"name": "太极实业", "ticker": "600667.SS", "price": 9.59,
         "target": 14.0, "stop_loss": 7.5, "win_rate": 0.55},
        ...
    ]

    返回按Kelly从高到低排序的结果列表。
    """
    results = []
    for c in candidates:
        odds = calc_odds(c["price"], c["target"], c["stop_loss"])
        kelly = calc_kelly(odds, c["win_rate"])
        half_kelly = kelly / 2
        position = calc_position(kelly, total_capital, half=True)

        results.append({
            **c,
            "odds": round(odds, 2),
            "kelly_pct": round(kelly * 100, 1),
            "half_kelly_pct": round(half_kelly * 100, 1),
            "position": position,
            "verdict": "BUY" if position >= 3000 else "SKIP" if kelly > 0 else "NO BET",
        })

    return sorted(results, key=lambda x: x["kelly_pct"], reverse=True)


def format_kelly_table(results: list[dict], total_capital: float = 30000) -> str:
    """格式化Kelly分析结果为文本表格"""
    lines = []
    lines.append(f"Kelly Analysis (Capital: {total_capital:,.0f})")
    lines.append("=" * 80)
    lines.append(f"{'Name':<12} {'Price':>8} {'Target':>8} {'Stop':>8} {'Odds':>6} {'Kelly':>7} {'Amount':>8} {'Verdict'}")
    lines.append("-" * 80)

    total_allocated = 0
    for r in results:
        lines.append(
            f"{r['name']:<12} {r['price']:>8.2f} {r['target']:>8.2f} "
            f"{r['stop_loss']:>8.2f} {r['odds']:>6.2f} {r['kelly_pct']:>6.1f}% "
            f"{r['position']:>8,} {r['verdict']}"
        )
        if r['verdict'] == 'BUY':
            total_allocated += r['position']

    lines.append("-" * 80)
    lines.append(f"{'Allocated:':<52} {total_allocated:>8,}")
    lines.append(f"{'Cash reserve:':<52} {total_capital - total_allocated:>8,}")
    lines.append("")
    return "\n".join(lines)


# ─── CLI ───────────────────────────────────────────────────────

def main():
    """交互式计算单个标的的Kelly"""
    if len(sys.argv) >= 5:
        # 命令行模式: python tools/kelly.py <price> <target> <stop> <win_rate> [capital]
        price = float(sys.argv[1])
        target = float(sys.argv[2])
        stop = float(sys.argv[3])
        win_rate = float(sys.argv[4])
        capital = float(sys.argv[5]) if len(sys.argv) > 5 else 30000

        odds = calc_odds(price, target, stop)
        kelly = calc_kelly(odds, win_rate)
        pos = calc_position(kelly, capital, half=True)

        print(f"Price: {price:.2f} | Target: {target:.2f} | Stop: {stop:.2f}")
        print(f"Odds: {odds:.2f} | Win Rate: {win_rate:.0%}")
        print(f"Kelly: {kelly:.1%} | Half-Kelly: {kelly/2:.1%}")
        print(f"Position ({capital:,.0f} capital): {pos:,}")
        print(f"Verdict: {'BUY' if pos >= 3000 else 'SKIP' if kelly > 0 else 'NO BET'}")
    else:
        print("Usage: python tools/kelly.py <price> <target> <stop_loss> <win_rate> [capital]")
        print("Example: python tools/kelly.py 9.59 14.0 7.5 0.55 30000")


if __name__ == "__main__":
    main()
