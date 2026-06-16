"""把 High 池的多张筹码图拼成 1 张总览长图 (网格), 供推送嵌入。

输出: output/overview_YYYYMMDD.png (覆盖式, 单文件不膨胀)。
"""

from __future__ import annotations

import os
from datetime import datetime

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib import font_manager  # noqa: E402
import matplotlib.image as mpimg  # noqa: E402

OUTPUT_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "output")
CHART_DIR = os.path.join(OUTPUT_DIR, "charts")

for _f in ("Microsoft YaHei", "SimHei", "DejaVu Sans"):
    if any(_f in f.name for f in font_manager.fontManager.ttflist):
        plt.rcParams["font.sans-serif"] = [_f]
        break
plt.rcParams["axes.unicode_minus"] = False


def build_overview(recs: list[dict], cols: int = 4) -> str | None:
    """把 recs 对应的 charts/{code}.png 拼成网格总览图。返回路径。"""
    items = [(r["code"], r.get("name", "")) for r in recs
             if os.path.exists(os.path.join(CHART_DIR, f"{r['code']}.png"))]
    if not items:
        return None

    n = len(items)
    rows = (n + cols - 1) // cols
    fig, axes = plt.subplots(rows, cols, figsize=(cols * 3.2, rows * 4.0))
    axes = axes.flatten() if n > 1 else [axes]

    for ax in axes:
        ax.axis("off")
    for i, (code, name) in enumerate(items):
        img = mpimg.imread(os.path.join(CHART_DIR, f"{code}.png"))
        axes[i].imshow(img)
        axes[i].set_title(f"{i + 1}. {code} {name}", fontsize=9)

    ts = datetime.now().strftime("%Y%m%d")
    fig.suptitle(f"单峰密集 Top{n}  {datetime.now():%Y-%m-%d}", fontsize=14)
    fig.tight_layout(rect=(0, 0, 1, 0.98))
    path = os.path.join(OUTPUT_DIR, f"overview_{ts}.png")
    fig.savefig(path, dpi=90, bbox_inches="tight")
    plt.close(fig)
    return path


if __name__ == "__main__":
    import sys
    sys.path.insert(0, os.path.dirname(__file__))
    import state_db as db
    import orchestrator as o
    conn = db.connect()
    _, recs = o.export_high(conn)
    p = build_overview(recs)
    print(f"总览图 -> {p}")
