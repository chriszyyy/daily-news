"""
板块 PE 历史分位扫描器 — 找"市盈率相对在低点"的公司。

思路:
  1. 取目标概念/行业板块的全部成分股(东财)
  2. 对每只股拉近十年 PE(TTM)历史(百度估值)
  3. 计算【当前 PE 在自身历史中的分位数】(percentile)
     - 分位越低 = 相对自己越便宜(真·相对低点)
  4. 过滤亏损股(PE<=0),按分位升序输出

为什么用历史分位而非绝对 PE:
  银行 PE 5 不代表便宜,半导体 PE 40 可能是历史底部。
  "相对低点"= 当前估值处于自身历史区间的低位。

用法:
  python tools/scanner/pe_percentile_scan.py --board 机器人概念
  python tools/scanner/pe_percentile_scan.py --board 机器人概念 人形机器人 --max-pct 30
  python tools/scanner/pe_percentile_scan.py --board 半导体 --type industry

依赖: akshare
"""
import argparse
import io
import json
import os
import sys
import time
import urllib.request
from datetime import datetime, timezone, timedelta

import akshare as ak

if hasattr(sys.stdout, "buffer"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

BJT = timezone(timedelta(hours=8))


def retry(fn, n=4, sleep=4, label=""):
    """带退避重试,返回结果或 None。"""
    last = None
    for i in range(n):
        try:
            return fn()
        except Exception as e:
            last = e
            if i < n - 1:
                time.sleep(sleep)
    print(f"  [warn] {label} 失败 {n} 次: {type(last).__name__}: {last}", flush=True)
    return None


def _board_code_cache():
    if not hasattr(_board_code_cache, "_c"):
        _board_code_cache._c = {}
    return _board_code_cache._c


def resolve_board_code(board: str, board_type: str) -> str | None:
    """板块名 → BKxxxx 代码。已是 BK 代码则直接返回。"""
    if board.upper().startswith("BK"):
        return board.upper()
    cache = _board_code_cache()
    key = (board_type, board)
    if key in cache:
        return cache[key]
    if board_type == "concept":
        fn = lambda: ak.stock_board_concept_name_em()
    else:
        fn = lambda: ak.stock_board_industry_name_em()
    df = retry(fn, label=f"板块列表[{board_type}]")
    if df is None:
        return None
    hit = df[df["板块名称"] == board]
    if hit.empty:
        hit = df[df["板块名称"].str.contains(board, na=False)]
    if hit.empty:
        print(f"  [warn] 未找到板块: {board}", flush=True)
        return None
    code = str(hit.iloc[0]["板块代码"])
    cache[key] = code
    return code


def _push2_page(board_code: str, page: int, pz: int = 100) -> tuple[list, int]:
    url = (
        f"https://push2.eastmoney.com/api/qt/clist/get?"
        f"pn={page}&pz={pz}&po=1&np=1&ut=bd1d9ddb04089700cf9c27f6f7426281"
        f"&fltt=2&invt=2&fs=b:{board_code}"
        f"&fields=f12,f14,f2,f3,f9,f20,f100&_={int(time.time()*1000)}"
    )
    req = urllib.request.Request(url, headers={
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
        "Referer": "https://quote.eastmoney.com/center/gridlist.html",
    })
    raw = urllib.request.urlopen(req, timeout=15).read().decode("utf-8", "ignore")
    d = json.loads(raw).get("data") or {}
    return (d.get("diff") or []), d.get("total", 0)


def get_constituents(board: str, board_type: str = "concept") -> list[dict]:
    """取板块成分股(push2 直连 + 分页)→ [{code,name,cur_pe,change_pct,mktcap_yi}]。"""
    code = resolve_board_code(board, board_type)
    if not code:
        return []
    out, page, total = [], 1, None
    while True:
        diff = total_ = None
        for attempt in range(4):
            try:
                diff, total_ = _push2_page(code, page)
                break
            except Exception:
                time.sleep([4, 8, 15, 30][attempt])
        if diff is None:
            print(f"  [warn] 板块 {board} 第 {page} 页失败,停止", flush=True)
            break
        if total is None:
            total = total_
        for it in diff:
            out.append({
                "code": str(it.get("f12", "")).zfill(6),
                "name": it.get("f14", ""),
                "cur_pe": _num(it.get("f9")),
                "change_pct": _num(it.get("f3")),
                "mktcap_yi": _num(it.get("f20")),
            })
        if len(out) >= (total or 0) or len(diff) < 100:
            break
        page += 1
        time.sleep(1.5)
    return out


def _num(v):
    try:
        f = float(v)
        if f != f:  # nan
            return None
        return f
    except (TypeError, ValueError):
        return None


def percentile_of(series_vals: list[float], cur: float) -> float:
    """当前值在历史序列中的分位(% 比当前小的占比)。"""
    if not series_vals:
        return None
    below = sum(1 for v in series_vals if v < cur)
    return round(100.0 * below / len(series_vals), 1)


def pe_history_stats(code: str, period: str = "近十年") -> dict | None:
    """拉历史 PE(TTM),返回 {cur, pct, lo, hi, median, n}。"""
    fn = lambda: ak.stock_zh_valuation_baidu(
        symbol=code, indicator="市盈率(TTM)", period=period
    )
    df = retry(fn, n=3, sleep=3, label=f"PE历史[{code}]")
    if df is None or df.empty:
        return None
    vals = [v for v in df["value"].tolist() if _num(v) is not None and v > 0]
    if len(vals) < 30:
        return None
    cur = vals[-1]  # 最新一条
    vals_sorted = sorted(vals)
    n = len(vals_sorted)
    median = vals_sorted[n // 2]
    return {
        "hist_cur_pe": round(cur, 2),
        "pe_pct": percentile_of(vals, cur),
        "pe_lo": round(min(vals), 2),
        "pe_hi": round(max(vals), 2),
        "pe_median": round(median, 2),
        "n_points": n,
    }


def _excluded_by_board(code: str, exclude: set) -> bool:
    """按代码前缀判断是否属于要排除的板块。"""
    code = code or ""
    if "star" in exclude and code.startswith(("688", "689")):
        return True  # 科创板
    if "chinext" in exclude and code.startswith(("300", "301")):
        return True  # 创业板
    if "bse" in exclude and code.startswith(("4", "8", "920", "92")):
        return True  # 北交所
    return False


def scan(boards: list[str], board_type: str, period: str,
         max_pct: float, sleep: float, min_cap_yi: float,
         exclude: set) -> tuple[list, list]:
    # 1) 汇总成分股(多板块去重)
    seen = {}
    for b in boards:
        print(f"[1] 抓取板块成分股: {b} ({board_type})", flush=True)
        cons = get_constituents(b, board_type)
        print(f"    → {len(cons)} 只", flush=True)
        for c in cons:
            if c["code"] and c["code"] not in seen:
                c["boards"] = [b]
                seen[c["code"]] = c
            elif c["code"]:
                seen[c["code"]]["boards"].append(b)
        time.sleep(sleep)

    universe = list(seen.values())
    # 板块过滤(科创板/创业板/北交所)
    if exclude:
        before = len(universe)
        universe = [u for u in universe
                    if not _excluded_by_board(u.get("code", ""), exclude)]
        print(f"[1a] 排除 {sorted(exclude)}: {before} → {len(universe)} 只", flush=True)
    # 市值下限过滤(亿元),减少微盘噪音 + 加速
    if min_cap_yi > 0:
        before = len(universe)
        universe = [u for u in universe
                    if (u.get("mktcap_yi") or 0) / 1e8 >= min_cap_yi]
        print(f"[1b] 市值 >= {min_cap_yi}亿 过滤: {before} → {len(universe)} 只", flush=True)
    print(f"[2] 去重后 {len(universe)} 只,逐股拉 PE 历史分位...", flush=True)

    results = []
    for i, stock in enumerate(universe, 1):
        code = stock["code"]
        stats = pe_history_stats(code, period)
        if stats:
            stock.update(stats)
        else:
            stock.update({"hist_cur_pe": None, "pe_pct": None})
        results.append(stock)
        if i % 10 == 0 or i == len(universe):
            print(f"    {i}/{len(universe)} 完成", flush=True)
        time.sleep(sleep)

    # 3) 过滤 + 排序:有分位、当前 PE>0、分位 <= max_pct
    valued = [
        r for r in results
        if r.get("pe_pct") is not None
        and r.get("hist_cur_pe") is not None
        and r["hist_cur_pe"] > 0
    ]
    valued.sort(key=lambda r: r["pe_pct"])
    return valued, results


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--board", nargs="+", required=True,
                   help="板块名(可多个),如: 机器人概念 人形机器人")
    p.add_argument("--type", dest="board_type", default="concept",
                   choices=["concept", "industry"], help="concept=概念板块 / industry=行业板块")
    p.add_argument("--period", default="近十年",
                   choices=["近一年", "近三年", "近五年", "近十年", "全部"])
    p.add_argument("--max-pct", type=float, default=100.0,
                   help="只显示 PE 分位 <= 此值的(默认全显示;低点常用 20-30)")
    p.add_argument("--sleep", type=float, default=1.0, help="每股间隔秒")
    p.add_argument("--min-cap", type=float, default=50.0,
                   help="市值下限(亿元),过滤微盘,默认50;设0不过滤")
    p.add_argument("--exclude", default="star,chinext,bse",
                   help="排除板块,逗号分隔: star=科创板 chinext=创业板 bse=北交所;"
                        "默认只留主板。设 none 不排除")
    p.add_argument("--out", default=None)
    args = p.parse_args()

    now = datetime.now(BJT)
    today = now.strftime("%Y-%m-%d")

    exclude = set()
    if args.exclude and args.exclude.lower() != "none":
        exclude = {x.strip().lower() for x in args.exclude.split(",") if x.strip()}

    print(f"[start] 板块={args.board} 类型={args.board_type} 周期={args.period} "
          f"分位阈值<={args.max_pct}% 排除={sorted(exclude) or '无'}  "
          f"{now:%Y-%m-%d %H:%M BJT}\n", flush=True)

    valued, allres = scan(args.board, args.board_type, args.period,
                          args.max_pct, args.sleep, args.min_cap, exclude)

    shown = [r for r in valued if r["pe_pct"] <= args.max_pct]

    lines = []
    lines.append("=" * 78)
    lines.append(f"【{' + '.join(args.board)}】PE 历史分位扫描 ({args.period}) — 按分位升序")
    lines.append(f"共 {len(allres)} 只,有效估值 {len(valued)} 只,"
                 f"分位<= {args.max_pct}% 命中 {len(shown)} 只")
    lines.append(f"扫描时间: {now:%Y-%m-%d %H:%M BJT}")
    lines.append("=" * 78)
    lines.append(f"{'代码':<7} {'名称':<9} {'当前PE':>8} {'历史分位':>7} "
                 f"{'区间低':>8} {'中位':>8} {'区间高':>9} {'今日%':>7} {'市值亿':>8}")
    lines.append("-" * 78)
    for r in shown:
        name = (r["name"] or "")
        cap_yi = (r.get("mktcap_yi") or 0) / 1e8
        lines.append(
            f"{r['code']:<7} {name:<9} {r['hist_cur_pe']:>8.1f} "
            f"{r['pe_pct']:>6.1f}% {r['pe_lo']:>8.1f} {r['pe_median']:>8.1f} "
            f"{r['pe_hi']:>9.1f} {(r.get('change_pct') or 0):>6.2f}% {cap_yi:>8.0f}"
        )
    lines.append("-" * 78)
    lines.append("分位<20% = 当前 PE 处于自身历史低位(相对低点)")
    lines.append("⚠ 分位低也可能是业绩恶化/盈利下滑导致,需结合基本面核实")
    report_txt = "\n".join(lines)
    print(report_txt)

    # 写 CSV
    if args.out is None:
        out_dir = os.path.join(os.path.dirname(__file__), "output")
        os.makedirs(out_dir, exist_ok=True)
        tag = "_".join(args.board)
        args.out = os.path.join(out_dir, f"pe_pct_{tag}_{today}.csv")
    import csv
    cols = ["code", "name", "boards", "hist_cur_pe", "pe_pct", "pe_lo",
            "pe_median", "pe_hi", "n_points", "change_pct", "mktcap_yi"]
    with open(args.out, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(cols)
        for r in valued:
            w.writerow([
                r.get("code"), r.get("name"),
                "|".join(r.get("boards", [])),
                r.get("hist_cur_pe"), r.get("pe_pct"), r.get("pe_lo"),
                r.get("pe_median"), r.get("pe_hi"), r.get("n_points"),
                r.get("change_pct"), r.get("mktcap_yi"),
            ])
    txt_path = os.path.splitext(args.out)[0] + ".txt"
    with open(txt_path, "w", encoding="utf-8") as f:
        f.write(report_txt + "\n")
    print(f"\n[done] CSV(全部估值) → {args.out}")
    print(f"[done] 文本报告 → {txt_path}")


if __name__ == "__main__":
    main()
