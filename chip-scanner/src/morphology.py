"""形态终审 — 在筹码分布数值上判定"单峰 vs 多峰"(纯 numpy, 无需图像/AI)。

直接分析 SCR 算法的 价格→筹码量 分布:
  1. 高斯平滑去噪。
  2. 找显著局部峰 (相对主峰高度 >= PEAK_REL, 间距 >= MIN_GAP)。
  3. 单峰度评分: 主峰占比 + 次峰压制程度。

判定"完美低位单峰套牢盘":
  - 单峰 (显著峰数 == 1) 或 主峰极度主导 (主峰筹码占比 >= DOMINANCE)
  - 且 现价 <= 主峰价格 (低位, 主力成本在上方=套牢)

输出 verdict: PASS(完美单峰) / WEAK(主导但有次峰) / FAIL(多峰/形态差)。
"""

from __future__ import annotations

import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(__file__))
import chip_calc  # noqa: E402

PEAK_REL = 0.35        # 次峰高度 >= 主峰 35% 才算显著峰
MIN_GAP_FRAC = 0.05    # 峰间最小间距 (占价格区间比例)
SMOOTH_FRAC = 0.04     # 平滑窗口占价格区间比例 (自适应, 接近视觉粒度)
DOMINANCE = 0.55       # 主峰邻域筹码占比阈值 (单峰主导)
PEAK_NBHD_FRAC = 0.12  # 主峰邻域宽度 (占价格区间)


def _smooth(y: np.ndarray, win: int) -> np.ndarray:
    if win < 3:
        return y
    k = np.ones(win) / win
    return np.convolve(y, k, mode="same")


def _find_peaks(y: np.ndarray, min_gap: int) -> list[int]:
    """局部极大值 (严格大于邻点), 再按间距去重保留较高者。"""
    idx = [i for i in range(1, len(y) - 1)
           if y[i] > y[i - 1] and y[i] >= y[i + 1]]
    idx.sort(key=lambda i: y[i], reverse=True)
    kept: list[int] = []
    for i in idx:
        if all(abs(i - j) >= min_gap for j in kept):
            kept.append(i)
    return sorted(kept)


def analyze(code: str) -> dict | None:
    kline = chip_calc.fetch_kline(code)
    dist = chip_calc.compute_distribution(kline) if kline else None
    if dist is None:
        return None
    grid, chips, m = dist
    n = len(grid)
    ys = _smooth(chips, max(int(n * SMOOTH_FRAC), 5))

    min_gap = max(int(n * MIN_GAP_FRAC), 1)
    peaks = _find_peaks(ys, min_gap)
    if not peaks:
        return {"code": code, "verdict": "FAIL", "n_peaks": 0,
                "reason": "无明显峰", **m}

    main = max(peaks, key=lambda i: ys[i])
    main_h = ys[main]
    sig_peaks = [p for p in peaks if ys[p] >= main_h * PEAK_REL]
    main_price = float(grid[main])

    # 主峰邻域筹码占比
    half = int(n * PEAK_NBHD_FRAC / 2)
    lo, hi = max(0, main - half), min(n, main + half + 1)
    dominance = float(chips[lo:hi].sum())
    n_sig = len(sig_peaks)

    # 新策略: 只看单峰密集, 不看低位/套牢
    if n_sig == 1 or dominance >= DOMINANCE:
        verdict = "PASS" if n_sig == 1 else "WEAK"
    else:
        verdict = "FAIL"
    reason = (f"显著峰{n_sig}, 主峰占比{dominance:.0%}, "
              f"主峰价{main_price:.2f}, SCR70={m.get('SCR70')}")

    return {
        "code": code, "verdict": verdict, "n_peaks": n_sig,
        "主峰价": round(main_price, 2), "主峰占比": round(dominance, 3),
        "reason": reason, "SCR70": m.get("SCR70"), "SCR": m["SCR"],
    }


def main() -> None:
    import argparse
    import state_db as db
    ap = argparse.ArgumentParser()
    ap.add_argument("codes", nargs="*")
    ap.add_argument("--high", action="store_true")
    args = ap.parse_args()

    targets = list(args.codes)
    if args.high:
        conn = db.connect()
        targets += [r["code"] for r in db.get_by_level(conn, "High")]
    if not targets:
        print("无目标。用 --high 或指定代码。")
        return

    print(f"{'代码':<8}{'判定':<7}{'峰数':<5}{'主峰价':<8}"
          f"{'主峰占比':<9}{'SCR':<7}{'套牢':<7}说明")
    for code in targets:
        r = analyze(code)
        if r is None:
            print(f"{code:<8}无数据")
            continue
        print(f"{r['code']:<8}{r['verdict']:<7}{r['n_peaks']:<5}"
              f"{r.get('主峰价',''):<8}{r.get('主峰占比',''):<9}"
              f"{r.get('SCR',''):<7}{r.get('套牢比例',''):<7}{r['reason']}")


if __name__ == "__main__":
    main()
