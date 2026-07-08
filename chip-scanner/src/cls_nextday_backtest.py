"""财联社电报 → 关联个股次日上涨 回测研究。

研究问题:财联社快讯提及某只 A 股 (常伴随盘中大涨) 之后, 该股次日 (T+1)
相对 T 日收盘是否上涨 > +1%? 并统计哪些"快讯模式"对次日上涨更有预测力
——尤其是"快讯当时该股已大涨 (RiseRange 高)"是否会次日追涨还是回落。

方法 (严防未来函数):
  1. 快讯源: 财联社电报 roll 接口 (www.cls.cn), 按 last_time 往前翻历史。
     每条快讯自带 stock_list (关联个股, 含 StockID + RiseRange 盘中涨幅)。
  2. 事件单元 = (一条快讯, 其关联的一只 A 股)。仅取 sh/sz 个股。
  3. 触发日映射 T: 快讯发布时间 >= 15:00 (收盘后) 或落在非交易日 → 顺延到
     下一交易日; 否则 T = 快讯当日。 (复用 news_nextday_backtest.map_trigger_day)
  4. 结果标签: 次日收益 = close(T+1)/close(T)-1; 上涨(win) = 次日收益 > +1%。
  5. 基准: 沪深300 (000300) 同 T 次日收益 + 个股无条件次日基准率。
  6. 模式特征:
     - RiseRange 桶: 快讯当时盘中涨幅 (<0 / 0-3% / 3-6% / 6-9% / 涨停≥9.5%)
       —— 核心: "快讯提到已大涨的股, 次日还涨吗"。
     - level A/B (重要红标) vs C (普通)。
     - 命中行业主题词 vs 未命中 (复用 cls_telegraph.THEME_KEYWORDS)。
     - 情绪 (复用 news_nextday_backtest 的关键词词典)。
     - 快讯正文含"涨停/大涨/飙升"字样 vs 无。

数据源:
  - 快讯: 财联社 roll 接口 (复用 cls_telegraph._sign / HEADERS / CLS_URL)。
  - 行情/日历: 腾讯日 K (复用 news_nextday_backtest.fetch_kline_dated)。

用法:
  python src/cls_nextday_backtest.py --days 30
  python src/cls_nextday_backtest.py --start 2026-06-01 --end 2026-07-08 --throttle 0.4
"""

from __future__ import annotations

import argparse
import os
import sys
import time
from datetime import date, datetime, timedelta
from urllib.parse import urlencode

import pandas as pd
import requests

_SRC_DIR = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_SRC_DIR)
OUTPUT_DIR = os.path.join(_ROOT, "output")
sys.path.insert(0, _SRC_DIR)

import cls_telegraph as CLS          # noqa: E402  签名/接口/主题词
import news_nextday_backtest as NB   # noqa: E402  kline/映射/基准/胜率

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:  # noqa: BLE001
        pass

# 快讯正文的"大涨"口语词 (作为附加特征)
SURGE_WORDS = ["涨停", "大涨", "飙升", "暴涨", "拉升", "新高", "封板", "涨超"]


def log(msg: str) -> None:
    print(f"{datetime.now():%H:%M:%S} {msg}", flush=True)


# ----------------------------- 财联社历史抓取 -----------------------------

def fetch_telegraph_history(start: str, end: str, throttle: float = 0.4,
                            max_pages: int = 400, rn: int = 50) -> list[dict]:
    """按 last_time 往前翻页, 收集 [start, end] 区间内的快讯 (原始 item)。

    start/end: 'YYYY-MM-DD'。翻到最老 ctime < start 或到 max_pages 停止。
    """
    start_ts = int(datetime.strptime(start, "%Y-%m-%d").timestamp())
    end_ts = int((datetime.strptime(end, "%Y-%m-%d") + timedelta(days=1)).timestamp())
    out: list[dict] = []
    seen_ids: set = set()
    last_time = ""
    for page in range(max_pages):
        params = {
            "app": "CailianpressWeb", "os": "web", "sv": "7.7.5",
            "category": "", "last_time": str(last_time) if last_time else "",
            "refresh_type": "1", "rn": str(rn),
        }
        url = CLS.CLS_URL + "?" + urlencode(CLS._sign(params))
        try:
            r = requests.get(url, headers=CLS.HEADERS, timeout=15)
            items = r.json().get("data", {}).get("roll_data", []) or []
        except Exception as e:  # noqa: BLE001
            log(f"  翻页 {page} 失败: {type(e).__name__} {e}")
            break
        if not items:
            break
        cts = [it.get("ctime") for it in items if it.get("ctime")]
        if not cts:
            break
        for it in items:
            cid = it.get("id")
            ct = it.get("ctime")
            if cid in seen_ids or not ct:
                continue
            seen_ids.add(cid)
            if start_ts <= ct < end_ts:
                out.append(it)
        page_min = min(cts)
        if page % 10 == 0:
            log(f"  翻页 {page}: 累计 {len(out)} 条 (最老 "
                f"{datetime.fromtimestamp(page_min):%m-%d %H:%M})")
        if page_min < start_ts:      # 已翻过起始日, 停止
            break
        last_time = page_min
        time.sleep(throttle)
    log(f"历史抓取完成: 区间内 {len(out)} 条快讯")
    return out


# ----------------------------- 事件构建 -----------------------------

def _a_share_stocks(item: dict) -> list[dict]:
    """从 stock_list 提取 A 股 (sh/sz), 返回 [{code, name, rise}]。"""
    res = []
    for s in (item.get("stock_list") or []):
        if not isinstance(s, dict):
            continue
        sid = str(s.get("StockID") or "")
        if not (sid.startswith("sh") or sid.startswith("sz")):
            continue          # 排除 港股/美股/指数
        code = sid[2:]
        if len(code) != 6 or not code.isdigit():
            continue
        res.append({
            "code": code,
            "name": s.get("name") or "",
            "rise": s.get("RiseRange"),   # 快讯当时盘中涨幅 %
        })
    return res


def build_events(items: list[dict], throttle: float) -> pd.DataFrame:
    """(快讯 × 关联A股) → 触发日 → 次日收益 → 事件表。kline 带缓存。"""
    kline_cache: dict[str, list[dict] | None] = {}

    def get_kline(code: str):
        if code not in kline_cache:
            kline_cache[code] = NB.fetch_kline_dated(code)
            time.sleep(throttle)
        return kline_cache[code]

    records: list[dict] = []
    total = len(items)
    for i, it in enumerate(items, 1):
        ct = it.get("ctime")
        if not ct:
            continue
        ndt = datetime.fromtimestamp(ct)
        stocks = _a_share_stocks(it)
        if not stocks:
            continue
        level = str(it.get("level") or "C")
        content = (it.get("content") or it.get("brief") or "").strip()
        themes = CLS._matched_themes(it)
        senti = NB.sentiment("", content)
        surge = any(w in content for w in SURGE_WORDS)
        for st in stocks:
            code = st["code"]
            dated = get_kline(code)
            if not dated:
                continue
            trading_dates = [d["date"] for d in dated]
            T = NB.map_trigger_day(ndt, trading_dates)
            if not T:
                continue
            nd = NB.next_day_return(dated, T)
            if nd["ret_pct"] is None:
                continue
            records.append({
                "code": code, "name": st["name"],
                "news_time": ndt.strftime("%Y-%m-%d %H:%M:%S"),
                "trigger_day": T, "t1_date": nd["t1_date"],
                "ret_pct": nd["ret_pct"],
                "win": nd["ret_pct"] > NB.WIN_THRESHOLD_PCT,
                "rise_at_news": st["rise"],
                "level": level,
                "important": level in CLS.IMPORTANT_LEVELS,
                "theme_hit": bool(themes),
                "themes": "/".join(themes[:4]),
                "sentiment": senti,
                "surge_word": surge,
                "content": content[:120],
            })
        if i % 50 == 0 or i == total:
            log(f"[{i}/{total}] 累计事件 {len(records)}")
    return pd.DataFrame(records)


# ----------------------------- 分析 -----------------------------

def _rise_bucket(v) -> str:
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return "无涨幅"
    try:
        r = float(v)
    except (ValueError, TypeError):
        return "无涨幅"
    if r < 0:
        return "下跌"
    if r < 3:
        return "0-3%"
    if r < 6:
        return "3-6%"
    if r < 9.5:
        return "6-9.5%"
    return "涨停≥9.5%"


def analyze(df: pd.DataFrame, bench: pd.DataFrame | None) -> None:
    if df.empty:
        log("无事件, 无法分析")
        return
    W = NB._winrate_line
    log("=" * 92)
    log(f"总事件 {len(df)}  覆盖 {df['code'].nunique()} 只  "
        f"区间 {df['trigger_day'].min()} ~ {df['trigger_day'].max()}")
    log(f"WIN 定义: 次日 close(T+1)/close(T)-1 > +{NB.WIN_THRESHOLD_PCT}%")
    log("-" * 92)
    log(f"[全样本]              {W(df['ret_pct'])}")

    log("\n[按快讯当时盘中涨幅 RiseRange 分桶] ← 核心: 已大涨的股次日还涨吗")
    df = df.copy()
    df["rise_bucket"] = df["rise_at_news"].map(_rise_bucket)
    for b in ["下跌", "0-3%", "3-6%", "6-9.5%", "涨停≥9.5%", "无涨幅"]:
        sub = df[df["rise_bucket"] == b]
        if not sub.empty:
            log(f"  {b:<10}      {W(sub['ret_pct'])}")

    log("\n[按重要等级]")
    for lbl, mask in (("重要(A/B)", df["important"]), ("普通(C)", ~df["important"])):
        log(f"  {lbl:<10}      {W(df[mask]['ret_pct'])}")

    log("\n[命中行业主题词 vs 未命中]")
    for lbl, mask in (("主题命中", df["theme_hit"]), ("非主题", ~df["theme_hit"])):
        log(f"  {lbl:<10}      {W(df[mask]['ret_pct'])}")

    log("\n[按情绪]")
    for k in ("pos", "neg", "mixed", "neutral"):
        sub = df[df["sentiment"] == k]
        if not sub.empty:
            log(f"  {k:<8}        {W(sub['ret_pct'])}")

    log("\n[快讯正文含大涨词(涨停/大涨/飙升...) vs 无]")
    for lbl, mask in (("含大涨词", df["surge_word"]), ("无", ~df["surge_word"])):
        log(f"  {lbl:<10}      {W(df[mask]['ret_pct'])}")

    log("\n[组合: 重要 + 主题命中]")
    combo = df[df["important"] & df["theme_hit"]]
    log(f"  重要&主题      {W(combo['ret_pct'])}")

    if bench is not None and not bench.empty:
        log("\n[基准: 沪深300 同触发日次日收益]")
        merged = df.merge(bench, on="trigger_day", how="left", suffixes=("", "_bench"))
        b = merged["ret_pct_bench"].dropna()
        if len(b):
            log(f"  沪深300        n={len(b):>4}  次日均{b.mean():+6.2f}%  "
                f"上涨率{(b > 0).mean():5.0%}")
            excess = (merged["ret_pct"] - merged["ret_pct_bench"]).dropna()
            log(f"  个股-基准 超额  均{excess.mean():+6.2f}%  "
                f"跑赢率{(excess > 0).mean():5.0%}")
    log("=" * 92)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", type=int, default=14,
                    help="回看天数 (默认14; 与 --start 二选一)")
    ap.add_argument("--start", default="", help="起始日 YYYY-MM-DD (覆盖 --days)")
    ap.add_argument("--end", default=date.today().isoformat(), help="结束日 YYYY-MM-DD")
    ap.add_argument("--throttle", type=float, default=0.4, help="请求间隔秒")
    ap.add_argument("--max-pages", type=int, default=400, help="财联社最大翻页")
    ap.add_argument("--out", default="", help="事件明细 CSV 输出路径")
    args = ap.parse_args()

    start = args.start or (
        datetime.strptime(args.end, "%Y-%m-%d") - timedelta(days=args.days)
    ).strftime("%Y-%m-%d")
    log(f"财联社快讯次日回测 | 区间 {start} ~ {args.end}")

    items = fetch_telegraph_history(start, args.end, throttle=args.throttle,
                                    max_pages=args.max_pages)
    if not items:
        log("无快讯, 结束。")
        return
    df = build_events(items, args.throttle)
    if df.empty:
        log("无事件生成 (可能无关联 A 股或无 T+1)。")
        return

    bench = NB.bench_next_day_table(start, args.end)
    analyze(df, bench)

    os.makedirs(OUTPUT_DIR, exist_ok=True)
    out = args.out or os.path.join(
        OUTPUT_DIR, f"cls_nextday_{start.replace('-', '')}_"
        f"{args.end.replace('-', '')}.csv")
    df.sort_values(["trigger_day", "code"]).to_csv(out, index=False,
                                                    encoding="utf-8-sig")
    log(f"[output] 事件明细 → {out}")


if __name__ == "__main__":
    main()
