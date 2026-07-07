"""热门板块可视化: Top12 板块热度横向柱状图 + 今日主题热度条。

输入: export_sector_heat() 产出的 heat DataFrame (或 sector_heat_YYYYMMDD.csv)。
输出: output/sector_heat_YYYYMMDD.png (覆盖式, 单文件不膨胀), 供 Server酱 推送嵌入。

字段依赖 (来自 orchestrator.export_sector_heat):
  industry, 热度分, 排名, 排名变化, 成交额亿, 中位涨幅, 上涨占比, 主题匹配
"""

from __future__ import annotations

import os
from datetime import datetime

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib import font_manager  # noqa: E402
import pandas as pd  # noqa: E402

OUTPUT_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "output")

for _f in ("Microsoft YaHei", "SimHei", "DejaVu Sans"):
    if any(_f in f.name for f in font_manager.fontManager.ttflist):
        plt.rcParams["font.sans-serif"] = [_f]
        break
plt.rcParams["axes.unicode_minus"] = False

# 与 orchestrator.HOT_SECTOR_KEYWORDS 保持一致 (主题热度聚合依据)
THEME_KEYWORDS = (
    "半导体", "电子", "通信", "计算机", "光学", "元件",
    "电力", "电网", "自动化", "机器人", "通用设备", "专用设备",
)


def _rank_delta_label(v) -> tuple[str, str]:
    """排名变化 -> (文字, 颜色)。正=上升(红), 负=下降(绿), 0/NaN=持平(灰)。"""
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return "NEW", "#888888"
    v = int(round(v))
    if v > 0:
        return f"↑{v}", "#d62728"
    if v < 0:
        return f"↓{abs(v)}", "#2ca02c"
    return "—", "#888888"


def _theme_heat(heat: pd.DataFrame) -> pd.DataFrame:
    """按主题关键词聚合当日热度。返回 [主题, 板块数, 平均热度分, 成交额亿] 降序。"""
    rows = []
    for kw in THEME_KEYWORDS:
        m = heat[heat["industry"].astype(str).str.contains(kw, na=False)]
        if m.empty:
            continue
        rows.append({
            "主题": kw,
            "板块数": int(len(m)),
            "平均热度分": round(float(m["热度分"].mean()), 2),
            "成交额亿": round(float(m["成交额亿"].sum()), 1),
        })
    if not rows:
        return pd.DataFrame(columns=["主题", "板块数", "平均热度分", "成交额亿"])
    return (pd.DataFrame(rows)
            .sort_values("平均热度分", ascending=False)
            .reset_index(drop=True))


def build_sector_chart(heat: pd.DataFrame, topn: int = 12) -> str | None:
    """生成热门板块热度图。返回 PNG 路径, heat 为空返回 None。"""
    if heat is None or heat.empty or "热度分" not in heat.columns:
        return None

    top = heat.sort_values("热度分", ascending=False).head(topn).reset_index(drop=True)
    themes = _theme_heat(heat).head(8)

    n = len(top)
    n_theme = len(themes)
    # 上面板高度随板块数, 下面板主题热度条
    fig = plt.figure(figsize=(9, max(6.0, n * 0.55 + n_theme * 0.42 + 2.0)))
    gs = fig.add_gridspec(2, 1, height_ratios=[n, max(n_theme, 3)], hspace=0.32)

    # ---- 面板1: Top 板块热度横向柱状图 ----
    ax1 = fig.add_subplot(gs[0])
    y = range(n)
    scores = top["热度分"].tolist()
    # 颜色: 主题匹配的板块用暖色高亮
    theme_hit = top["主题匹配"].tolist() if "主题匹配" in top.columns else [False] * n
    colors = ["#ff7f0e" if h else "#4c78a8" for h in theme_hit]
    ax1.barh(list(y), scores, color=colors, height=0.68)
    ax1.invert_yaxis()  # 第1名在最上

    labels = []
    has_delta = "排名变化" in top.columns
    turn = top["成交额亿"].tolist() if "成交额亿" in top.columns else [None] * n
    for i in range(n):
        ind = str(top.loc[i, "industry"])
        labels.append(f"{i + 1}. {ind}")
        # 右侧标注: 热度分 + 排名变化 + 成交额
        parts = [f"{scores[i]:.1f}"]
        if has_delta:
            dtxt, dcol = _rank_delta_label(top.loc[i, "排名变化"])
            ax1.text(scores[i] + max(scores) * 0.015, i, dtxt,
                     va="center", ha="left", fontsize=9, color=dcol, fontweight="bold")
        tv = turn[i]
        score_txt = f"{scores[i]:.1f}"
        if tv is not None and not pd.isna(tv):
            score_txt += f"  {tv:.0f}亿"
        ax1.text(scores[i] * 0.5, i, score_txt, va="center", ha="center",
                 fontsize=8, color="white", fontweight="bold")

    ax1.set_yticks(list(y))
    ax1.set_yticklabels(labels, fontsize=9)
    ax1.set_xlabel("热度分 (橙=主题匹配, 右侧↑↓为排名变化)", fontsize=9)
    ax1.set_title(f"今日热门板块 Top{n}", fontsize=13, fontweight="bold")
    ax1.set_xlim(0, max(scores) * 1.18)
    ax1.grid(axis="x", alpha=0.25)

    # ---- 面板2: 今日主题热度 ----
    ax2 = fig.add_subplot(gs[1])
    if n_theme:
        ty = range(n_theme)
        tscores = themes["平均热度分"].tolist()
        ax2.barh(list(ty), tscores, color="#e45756", height=0.6)
        ax2.invert_yaxis()
        tlabels = []
        for i in range(n_theme):
            tlabels.append(str(themes.loc[i, "主题"]))
            cnt = int(themes.loc[i, "板块数"])
            turn_v = themes.loc[i, "成交额亿"]
            ax2.text(tscores[i] + max(tscores) * 0.015, i,
                     f"{tscores[i]:.1f}  {cnt}板块 {turn_v:.0f}亿",
                     va="center", ha="left", fontsize=8, color="#333333")
        ax2.set_yticks(list(ty))
        ax2.set_yticklabels(tlabels, fontsize=9)
        ax2.set_xlim(0, max(tscores) * 1.35)
        ax2.set_xlabel("主题平均热度分", fontsize=9)
        ax2.grid(axis="x", alpha=0.25)
    else:
        ax2.axis("off")
        ax2.text(0.5, 0.5, "无主题匹配板块", ha="center", va="center", fontsize=11)
    ax2.set_title("今日主题热度", fontsize=12, fontweight="bold")

    fig.suptitle(f"板块热度总览  {datetime.now():%Y-%m-%d}", fontsize=14, y=0.995)

    ts = datetime.now().strftime("%Y%m%d")
    path = os.path.join(OUTPUT_DIR, f"sector_heat_{ts}.png")
    fig.savefig(path, dpi=100, bbox_inches="tight")
    plt.close(fig)
    return path


if __name__ == "__main__":
    import sys
    src = sys.argv[1] if len(sys.argv) > 1 else None
    if src and os.path.exists(src):
        df = pd.read_csv(src)
        out = build_sector_chart(df)
        print(out or "heat 为空, 未出图")
    else:
        print("用法: python sector_chart.py <sector_heat_YYYYMMDD.csv>")
