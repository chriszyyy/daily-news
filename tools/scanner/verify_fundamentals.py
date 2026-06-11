"""
对 PE 分位低的候选做"真便宜 vs 业绩坑"核实。

核心判据:PE 分位低有两种成因
  ① 价格下跌(E 稳定/小增)→ 可能真低估
  ② 净利润暴涨(E 变大把 PE 砸低)→ 周期/订单驱动,需警惕利润不可持续
  ③ 价格跌 + 利润同步下滑 → 价值陷阱(falling knife)

拉每只:近几期 营收/净利润 同比、ROE、毛利率、资产负债率,给出分类。

用法: python tools/scanner/verify_fundamentals.py 603025 688208 ...
"""
import sys, io, time, argparse
import akshare as ak

if hasattr(sys.stdout, "buffer"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")


def retry(fn, n=4, sleep=4):
    for i in range(n):
        try:
            return fn()
        except Exception:
            time.sleep(sleep)
    return None


def num(v):
    try:
        f = float(v)
        return f if f == f else None
    except (TypeError, ValueError):
        return None


def get_abstract(code):
    """财务摘要:返回 dict 指标名→最近几期值列表(列为报告期)。"""
    df = retry(lambda: ak.stock_financial_abstract(symbol=code))
    if df is None or df.empty:
        return None, None
    # 列形如 ['选项','指标', 报告期1, 报告期2...]
    cols = list(df.columns)
    date_cols = [c for c in cols if c not in ("选项", "指标")]
    date_cols = date_cols[:6]  # 最近6期(已按新→旧)
    out = {}
    for _, r in df.iterrows():
        ind = r.get("指标")
        out[ind] = [num(r.get(c)) for c in date_cols]
    return out, date_cols


def yoy(series, periods_per_year=None):
    """同比:用最新值 vs 4 期前(季报)。series 为新→旧。"""
    if not series or len(series) < 5 or series[0] is None or series[4] is None:
        # 退而求其次:最新 vs 上一期
        if series and len(series) >= 2 and series[0] is not None and series[1] is not None and series[1] != 0:
            return ("环比", round(100*(series[0]-series[1])/abs(series[1]), 1))
        return (None, None)
    if series[4] == 0:
        return (None, None)
    return ("同比", round(100*(series[0]-series[4])/abs(series[4]), 1))


def analyze(code):
    abs_, dates = get_abstract(code)
    if abs_ is None:
        return f"{code}: [数据失败]"
    # 常见指标名(akshare stock_financial_abstract)
    def pick(*names):
        for n in names:
            for k in abs_:
                if n in k:
                    return abs_[k]
        return None

    rev = pick("营业总收入", "营业收入")
    np_ = pick("归母净利润", "净利润")
    eps = pick("基本每股收益", "每股收益")
    roe = pick("净资产收益率")
    gpm = pick("毛利率", "销售毛利率")
    debt = pick("资产负债率")
    ocf = pick("经营现金流", "每股经营现金流")

    rev_lbl, rev_g = yoy(rev) if rev else (None, None)
    np_lbl, np_g = yoy(np_) if np_ else (None, None)

    latest_date = dates[0] if dates else "?"

    lines = [f"\n【{code}】最新报告期 {latest_date}"]
    def fmt(name, series, unit="", scale=1.0):
        if series and series[0] is not None:
            return f"  {name}: {series[0]/scale:,.2f}{unit}"
        return f"  {name}: -"
    lines.append(fmt("营业总收入", rev, " 亿", scale=1e8))
    if rev_g is not None:
        lines.append(f"    └ 营收{rev_lbl}: {rev_g:+.1f}%")
    lines.append(fmt("归母净利润", np_, " 亿", scale=1e8))
    if np_g is not None:
        lines.append(f"    └ 净利{np_lbl}: {np_g:+.1f}%")
    lines.append(fmt("净资产收益率ROE", roe, "%"))
    lines.append(fmt("毛利率", gpm, "%"))
    lines.append(fmt("资产负债率", debt, "%"))

    # 分类判据
    verdict = "数据不足"
    if np_g is not None:
        if np_g > 50:
            verdict = "⚠ 利润暴涨型(E↑砸低PE)— 查利润可持续性/是否周期峰值"
        elif np_g < -20:
            verdict = "🚩 利润下滑型 — 警惕价值陷阱(分位低因业绩恶化)"
        elif -20 <= np_g <= 20 and rev_g is not None and rev_g > 0:
            verdict = "✅ 利润平稳+营收增 — 分位低更可能是价格回调(真便宜候选)"
        else:
            verdict = "中性 — 需结合行业景气进一步看"
    lines.append(f"  → 判定: {verdict}")
    return "\n".join(lines)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("codes", nargs="+")
    args = p.parse_args()
    print("="*70)
    print("PE 分位低 — 真便宜 vs 业绩坑 核实")
    print("="*70)
    results = []
    for c in args.codes:
        r = analyze(c)
        print(r, flush=True)
        results.append(r)
        time.sleep(1.5)
    # 写文件
    import os
    out = os.path.join(os.path.dirname(__file__), "output", "verify_fundamentals.txt")
    with open(out, "w", encoding="utf-8") as f:
        f.write("="*70+"\nPE分位低 真便宜vs业绩坑 核实\n"+"="*70+"\n")
        f.write("\n".join(results))
    print(f"\n[done] → {out}")


if __name__ == "__main__":
    main()
