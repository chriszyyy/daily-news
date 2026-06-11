"""
后处理:从已生成的 PE 分位 CSV 中过滤板块,输出"只留主板"报告。
不重新拉数据,秒级完成。

用法:
  python tools/scanner/filter_mainboard.py output/pe_pct_机器人概念_2026-06-09.csv
  python tools/scanner/filter_mainboard.py output/pe_pct_*.csv --max-pct 20
"""
import argparse
import csv
import glob
import io
import os
import sys

if hasattr(sys.stdout, "buffer"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")


def board_of(code: str) -> str:
    code = (code or "").zfill(6)
    if code.startswith(("688", "689")):
        return "科创板"
    if code.startswith(("300", "301")):
        return "创业板"
    if code.startswith(("4", "8", "920", "92")):
        return "北交所"
    if code.startswith(("600", "601", "603", "605")):
        return "沪主板"
    if code.startswith(("000", "001", "002", "003")):
        return "深主板"
    return "其他"


MAINBOARD = {"沪主板", "深主板"}


def fnum(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def process(path: str, max_pct: float):
    rows = []
    with open(path, "r", encoding="utf-8-sig") as f:
        for r in csv.DictReader(f):
            rows.append(r)
    main = [r for r in rows if board_of(r.get("code", "")) in MAINBOARD]
    # 排序 by pe_pct
    def k(r):
        v = fnum(r.get("pe_pct"))
        return v if v is not None else 1e9
    main.sort(key=k)
    shown = [r for r in main if (fnum(r.get("pe_pct")) or 999) <= max_pct]

    base = os.path.basename(path).replace(".csv", "")
    title = base.replace("pe_pct_", "")
    lines = []
    lines.append("=" * 82)
    lines.append(f"【{title}】仅主板 PE 历史分位 — 按分位升序  (分位<= {max_pct}%)")
    lines.append(f"原 {len(rows)} 只 → 主板 {len(main)} 只 → 命中 {len(shown)} 只")
    lines.append("=" * 82)
    lines.append(f"{'代码':<7} {'名称':<9} {'板块':<6} {'当前PE':>8} {'分位':>7} "
                 f"{'区间低':>8} {'中位':>8} {'市值亿':>8}")
    lines.append("-" * 82)
    for r in shown:
        cap = fnum(r.get("mktcap_yi"))
        cap_yi = cap / 1e8 if cap else 0
        name = (r.get("name") or "")
        lines.append(
            f"{r.get('code',''):<7} {name:<9} {board_of(r.get('code','')):<6} "
            f"{(fnum(r.get('hist_cur_pe')) or 0):>8.1f} "
            f"{(fnum(r.get('pe_pct')) or 0):>6.1f}% "
            f"{(fnum(r.get('pe_lo')) or 0):>8.1f} "
            f"{(fnum(r.get('pe_median')) or 0):>8.1f} {cap_yi:>8.0f}"
        )
    lines.append("-" * 82)
    lines.append("已排除: 科创板(688/689) + 创业板(300/301) + 北交所")
    lines.append("⚠ 分位低 ≠ 一定便宜:需财务核实(利润暴涨砸低 / 业绩恶化陷阱)")
    report = "\n".join(lines)

    out = path.replace(".csv", "_主板.txt")
    with open(out, "w", encoding="utf-8") as f:
        f.write(report + "\n")
    print(report)
    print(f"\n[saved] {out}\n")


def main():
    p = argparse.ArgumentParser()
    p.add_argument("paths", nargs="+", help="CSV 路径(支持通配符)")
    p.add_argument("--max-pct", type=float, default=15.0)
    args = p.parse_args()
    files = []
    for pat in args.paths:
        files.extend(glob.glob(pat))
    if not files:
        print("无匹配文件")
        return
    for fp in sorted(set(files)):
        if fp.endswith(".csv"):
            process(fp, args.max_pct)


if __name__ == "__main__":
    main()
