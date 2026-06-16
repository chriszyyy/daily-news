"""筹码分布图绘制 — 把 SCR 算法的内部分布可视化为横向筹码图。

横轴=筹码量, 纵轴=价格 (券商筹码图标准布局)。
- 红色: 获利盘 (成本 < 现价)
- 蓝色: 套牢盘 (成本 >= 现价)
- 横线: 现价 / 平均成本 / 90% 成本上下沿

用途:
  1. 可视化验证 High 池标的是否真"低位单峰套牢"。
  2. 自绘图可直接喂给 AI/OpenCV 终审, 替代东吴秀财截图。

用法:
  python src/plot_chips.py [代码...]          # 指定代码
  python src/plot_chips.py --high             # 画当前 High 池全部
"""

from __future__ import annotations

import argparse
import os
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib import font_manager  # noqa: E402

sys.path.insert(0, os.path.dirname(__file__))
import chip_calc  # noqa: E402
import state_db as db  # noqa: E402

CHART_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)),
                         "output", "charts")

# 中文字体 (Windows 自带黑体)
for _f in ("Microsoft YaHei", "SimHei", "DejaVu Sans"):
    if any(_f in f.name for f in font_manager.fontManager.ttflist):
        plt.rcParams["font.sans-serif"] = [_f]
        break
plt.rcParams["axes.unicode_minus"] = False


def plot_one(code: str, name: str = "", win: int = None) -> str | None:
    kline = chip_calc.fetch_kline(code, lmt=win) if win else chip_calc.fetch_kline(code)
    dist = chip_calc.compute_distribution(kline) if kline else None
    if dist is None:
        print(f"[plot] {code} 无数据")
        return None
    grid, chips, m = dist
    cur = m["现价"]
    avg = m["平均成本"]

    fig, ax = plt.subplots(figsize=(6, 8))
    # 横向条: 获利(红)/套牢(蓝)
    colors = ["#d62728" if p < cur else "#1f77b4" for p in grid]
    ax.barh(grid, chips, height=(grid[1] - grid[0]) * 1.1,
            color=colors, linewidth=0)

    ax.axhline(cur, color="black", lw=1.4, ls="-",
               label=f"现价 {cur:.2f}")
    ax.axhline(avg, color="orange", lw=1.2, ls="--",
               label=f"平均成本 {avg:.2f}")
    ax.axhline(m["70成本低"], color="green", lw=0.9, ls=":",
               label=f"70%带 {m['70成本低']:.2f}~{m['70成本高']:.2f}")
    ax.axhline(m["70成本高"], color="green", lw=0.9, ls=":")

    title = (f"{code} {name}\n"
             f"主峰占比={m['主峰占比']:.0%}  带宽70={m['带宽70']:.1%}  "
             f"SCR70={m['SCR70']:.3f}")
    ax.set_title(title, fontsize=11)
    ax.set_xlabel("筹码量 (占比)")
    ax.set_ylabel("价格")
    ax.legend(loc="upper right", fontsize=9)
    ax.set_xticks([])
    fig.tight_layout()

    os.makedirs(CHART_DIR, exist_ok=True)
    path = os.path.join(CHART_DIR, f"{code}.png")
    fig.savefig(path, dpi=110)
    plt.close(fig)
    print(f"[plot] {code} {name} → {path}")
    return path


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("codes", nargs="*", help="股票代码")
    ap.add_argument("--high", action="store_true", help="画当前 High 池")
    args = ap.parse_args()

    targets = []
    if args.high:
        conn = db.connect()
        targets = [(r["code"], r["name"]) for r in db.get_by_level(conn, "High")]
    targets += [(c, "") for c in args.codes]

    if not targets:
        print("无目标。用 --high 或指定代码。")
        return
    for code, name in targets:
        plot_one(code, name)


if __name__ == "__main__":
    main()
