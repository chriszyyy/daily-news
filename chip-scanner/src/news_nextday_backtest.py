"""东方财富个股新闻 → 次日上涨 回测研究。

研究问题:某只 A 股出现东财新闻后, 次日 (T+1) 相对 T 日收盘是否上涨 > +1%?
并统计哪些"新闻模式"对次日上涨更有预测力。

方法 (严防未来函数):
  1. 新闻源: 东财搜索 API (search-api-web.eastmoney.com), 按代码搜, 带精确时间戳。
  2. 触发日映射 T: 新闻发布时间 >= 15:00 (收盘后) 或落在非交易日 → 顺延到下一
     交易日; 否则 T = 新闻当日。 (--close-cutoff 可调)
  3. 结果标签: 次日收益 = close(T+1)/close(T) - 1; 上涨(win) = 次日收益 > +1%。
  4. 基准: 沪深300 (000300) 同 T 的次日收益, 以及个股无条件次日基准率。
  5. 模式特征: 情绪关键词(利好/利空)、当日新闻条数(消息面热度)、
     标题含代码 vs 仅正文提及、媒体来源。

数据源:
  - 新闻: 东财搜索 jsonp (分页, 按时间倒序)。
  - 行情/日历: 腾讯日 K (proxy.finance.qq.com, 复用 chip_calc.TX_URL)。

标的池:
  - 主源: chip-scanner 的 data/state.db 中 level IN ('Mid','High')。
  - 回退: --codes 手动指定, 或最新 output/*scan*.csv。

用法:
  python src/news_nextday_backtest.py --codes 600519,000799 \
      --start 2026-01-01 --end 2026-07-01 --throttle 0.5
  python src/news_nextday_backtest.py --universe state-db --start 2026-05-01
"""

from __future__ import annotations

import argparse
import json
import os
import random
import sqlite3
import sys
import time
import urllib.parse
import urllib.request
from datetime import date, datetime, timedelta

import pandas as pd

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:  # noqa: BLE001
        pass

_SRC_DIR = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_SRC_DIR)
OUTPUT_DIR = os.path.join(_ROOT, "output")
STATE_DB = os.path.join(_ROOT, "data", "state.db")

TX_URL = "https://proxy.finance.qq.com/ifzqgtimg/appstock/app/newfqkline/get"
NEWS_URL = "https://search-api-web.eastmoney.com/search/jsonp"

UA = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/121.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:120.0) Gecko/20100101 Firefox/120.0",
]

# 次日上涨阈值 (用户定义: > +1% 才算有意义的上涨)
WIN_THRESHOLD_PCT = 1.0
# 收盘时点: 该时间(含)之后的新闻视为"盘后", 触发日顺延
CLOSE_CUTOFF = "15:00"

# 情绪关键词词典 (粗粒度; 用于模式分组, 非精确 NLP)
POS_KEYWORDS = [
    "涨停", "中标", "签约", "增持", "回购", "预增", "扭亏", "收购", "合作",
    "订单", "利好", "突破", "新高", "获批", "量产", "投产", "提价", "涨价",
    "超预期", "创新高", "重组", "注入", "分红", "业绩", "净利", "大涨",
]
NEG_KEYWORDS = [
    "减持", "亏损", "商誉", "立案", "问询", "质押", "违规", "退市", "跌停",
    "下修", "风险", "处罚", "诉讼", "预亏", "警示", "冻结", "解禁", "套现",
    "大跌", "暴跌", "利空", "被查", "*ST", "ST", "停牌",
]


def log(msg: str) -> None:
    line = f"{datetime.now():%H:%M:%S} {msg}"
    print(line, flush=True)


def _tx_symbol(code: str) -> str:
    return f"{'sh' if code.startswith('6') else 'sz'}{code}"


# ----------------------------- 行情 / 交易日历 -----------------------------

def fetch_kline_dated(code: str, index: bool = False,
                      max_retries: int = 3) -> list[dict] | None:
    """拉带日期的日 K (旧→新)。返回 [{date, close, high, low, open}, ...]。

    腾讯日 K 行: [日期, 开, 收, 高, 低, 量, {}, 换手率, ...]。
    index=True 时 code 为指数 (如 沪深300=000300)。
    """
    if index:
        sym = f"sh{code}" if code.startswith(("000", "999")) else f"sz{code}"
    else:
        sym = _tx_symbol(code)
    start = date.today().replace(year=date.today().year - 2).isoformat()
    params = {"param": f"{sym},day,{start},2050-12-31,800,"}
    url = TX_URL + "?" + urllib.parse.urlencode(params)
    for attempt in range(max_retries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": random.choice(UA)})
            with urllib.request.urlopen(req, timeout=12) as r:
                data = json.loads(r.read().decode("utf-8", errors="ignore"))
            node = (data.get("data") or {}).get(sym) or {}
            rows = node.get("day") or node.get("qfqday")
            if not rows:
                return None
            out = []
            for p in rows:
                try:
                    out.append({
                        "date": p[0],
                        "open": float(p[1]),
                        "close": float(p[2]),
                        "high": float(p[3]),
                        "low": float(p[4]),
                    })
                except (ValueError, TypeError, IndexError):
                    continue
            return out or None
        except Exception:  # noqa: BLE001
            time.sleep(0.6 * (attempt + 1))
    return None


def next_day_return(dated: list[dict], trigger_date: str) -> dict:
    """给定触发日 T (交易日), 计算次日 (T+1) 相对 T 收盘的收益 %。

    返回 {trigger_close, t1_date, t1_close, ret_pct}。若无 T 或无 T+1 → 空值。
    """
    dates = [d["date"] for d in dated]
    # T = 第一个 >= trigger_date 的交易日 (trigger_date 本身可能非交易日, 前移已在映射处理)
    idx = None
    for i, d in enumerate(dates):
        if d == trigger_date:
            idx = i
            break
    if idx is None:
        return {"trigger_close": None, "t1_date": None, "t1_close": None, "ret_pct": None}
    if idx + 1 >= len(dated):
        return {"trigger_close": dated[idx]["close"], "t1_date": None,
                "t1_close": None, "ret_pct": None}
    t_close = dated[idx]["close"]
    t1 = dated[idx + 1]
    ret = (t1["close"] / t_close - 1) * 100 if t_close else None
    return {"trigger_close": t_close, "t1_date": t1["date"],
            "t1_close": t1["close"],
            "ret_pct": round(ret, 3) if ret is not None else None}


def map_trigger_day(news_dt: datetime, trading_dates: list[str],
                    cutoff: str = CLOSE_CUTOFF) -> str | None:
    """新闻时间 → 可操作的触发交易日 T。

    规则: 新闻时间 >= cutoff (盘后) 或落在非交易日 → T = 下一交易日;
          否则 T = 新闻当日 (须是交易日)。
    trading_dates: 升序交易日列表 (来自个股 K 线, 天然是交易日)。
    """
    tset = set(trading_dates)
    d = news_dt.strftime("%Y-%m-%d")
    ch, cm = (int(x) for x in cutoff.split(":"))
    after_close = (news_dt.hour, news_dt.minute) >= (ch, cm)
    if d in tset and not after_close:
        return d
    # 盘后 或 非交易日 → 顺延到第一个严格大于 d 的交易日
    for td in trading_dates:
        if td > d:
            return td
    return None


# ----------------------------- 新闻 (东财搜索 API) -----------------------------

def fetch_news(code: str, start: str, end: str, max_pages: int = 20,
               page_size: int = 20, throttle: float = 0.4) -> list[dict]:
    """按代码抓东财新闻 (时间倒序分页)。返回 [{date, title, content, media, url}]。

    在 [start, end] 区间内截取; 翻页直到早于 start 或到 max_pages。
    """
    out: list[dict] = []
    for page in range(1, max_pages + 1):
        param = {
            "uid": "",
            "keyword": code,
            "type": ["cmsArticleWebOld"],
            "client": "web", "clientType": "web", "clientVersion": "curr",
            "param": {"cmsArticleWebOld": {
                "searchScope": "default", "sort": "time",
                "pageIndex": page, "pageSize": page_size,
                "preTag": "<em>", "postTag": "</em>",
            }},
        }
        q = urllib.parse.urlencode({
            "cb": "cb",
            "param": json.dumps(param, ensure_ascii=False, separators=(",", ":")),
            "_": int(time.time() * 1000),
        })
        url = f"{NEWS_URL}?{q}"
        try:
            req = urllib.request.Request(url, headers={
                "User-Agent": random.choice(UA),
                "Referer": "https://so.eastmoney.com/",
            })
            with urllib.request.urlopen(req, timeout=12) as r:
                raw = r.read().decode("utf-8", errors="ignore")
        except Exception as e:  # noqa: BLE001
            log(f"  [news] {code} 第{page}页失败: {type(e).__name__}")
            break
        # 剥 jsonp 外壳 cb({...})
        s, e = raw.find("("), raw.rfind(")")
        if s < 0 or e < 0:
            break
        try:
            data = json.loads(raw[s + 1:e])
        except json.JSONDecodeError:
            break
        arts = ((data.get("result") or {}).get("cmsArticleWebOld")) or []
        if not arts:
            break
        page_min_date = None
        for a in arts:
            dt = _clean(a.get("date"))
            title = _strip_em(a.get("title"))
            content = _strip_em(a.get("content"))
            if not dt:
                continue
            page_min_date = dt if page_min_date is None else min(page_min_date, dt)
            day = dt[:10]
            if day < start or day > end:
                continue
            out.append({
                "date": dt, "title": title, "content": content,
                "media": _clean(a.get("mediaName")), "url": _clean(a.get("url")),
            })
        # 本页最旧新闻已早于 start → 停止翻页
        if page_min_date and page_min_date[:10] < start:
            break
        time.sleep(throttle)
    return out


def _clean(v) -> str:
    return str(v).strip() if v is not None else ""


def _strip_em(v) -> str:
    return _clean(v).replace("<em>", "").replace("</em>", "")


# ----------------------------- 特征 / 情绪 -----------------------------

def sentiment(title: str, content: str) -> str:
    """粗粒度情绪: pos / neg / mixed / neutral (基于关键词命中)。"""
    text = f"{title} {content}"
    pos = sum(1 for k in POS_KEYWORDS if k in text)
    neg = sum(1 for k in NEG_KEYWORDS if k in text)
    if pos and neg:
        return "mixed"
    if pos:
        return "pos"
    if neg:
        return "neg"
    return "neutral"


def title_has_code(title: str, code: str, name: str) -> bool:
    return code in title or (bool(name) and name in title)


# ----------------------------- 标的池 -----------------------------

def load_universe(source: str, codes_arg: str) -> list[tuple[str, str]]:
    """返回 [(code, name)]。source: 'codes' | 'state-db' | 'csv'。"""
    if source == "codes" or codes_arg:
        codes = [c.strip().zfill(6) for c in codes_arg.split(",") if c.strip()]
        return [(c, "") for c in codes]
    if source == "state-db":
        if not os.path.exists(STATE_DB):
            raise FileNotFoundError(
                f"state.db 不存在 ({STATE_DB}); 请先跑 chip-scanner 或用 --codes")
        conn = sqlite3.connect(STATE_DB)
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            "SELECT code, name FROM stocks WHERE level IN ('Mid','High')").fetchall()
        conn.close()
        if not rows:
            raise ValueError("state.db 中 Mid/High 池为空; 请先跑 chip-scanner 或用 --codes")
        return [(r["code"], r["name"] or "") for r in rows]
    if source == "csv":
        files = sorted(f for f in os.listdir(OUTPUT_DIR)
                       if "scan" in f and f.endswith(".csv"))
        if not files:
            raise FileNotFoundError("output/ 下无 *scan*.csv")
        df = pd.read_csv(os.path.join(OUTPUT_DIR, files[-1]), dtype={"code": str})
        df["code"] = df["code"].str.zfill(6)
        name_col = "name" if "name" in df.columns else df.columns[3]
        return list(zip(df["code"], df[name_col].fillna("")))
    raise ValueError(f"未知 universe 源: {source}")


# ----------------------------- 主流程 -----------------------------

def build_events(codes: list[tuple[str, str]], start: str, end: str,
                 throttle: float, max_pages: int) -> pd.DataFrame:
    """对每只股票: 抓新闻 → 映射触发日 → 算次日收益 → 组装事件表。"""
    records: list[dict] = []
    for i, (code, name) in enumerate(codes, 1):
        dated = fetch_kline_dated(code)
        if not dated:
            log(f"[{i}/{len(codes)}] {code} 无 K 线, 跳过")
            continue
        trading_dates = [d["date"] for d in dated]
        news = fetch_news(code, start, end, max_pages=max_pages, throttle=throttle)
        # 每个触发日的当日新闻条数 (消息面热度)
        per_day_count: dict[str, int] = {}
        mapped = []
        for a in news:
            try:
                ndt = datetime.strptime(a["date"], "%Y-%m-%d %H:%M:%S")
            except ValueError:
                continue
            T = map_trigger_day(ndt, trading_dates)
            if not T:
                continue
            per_day_count[T] = per_day_count.get(T, 0) + 1
            mapped.append((a, ndt, T))
        for a, ndt, T in mapped:
            nd = next_day_return(dated, T)
            if nd["ret_pct"] is None:
                continue
            records.append({
                "code": code, "name": name,
                "news_time": a["date"], "trigger_day": T,
                "t1_date": nd["t1_date"],
                "ret_pct": nd["ret_pct"],
                "win": nd["ret_pct"] > WIN_THRESHOLD_PCT,
                "sentiment": sentiment(a["title"], a["content"]),
                "title_hit": title_has_code(a["title"], code, name),
                "day_news_count": per_day_count.get(T, 1),
                "media": a["media"],
                "title": a["title"],
                "url": a["url"],
            })
        log(f"[{i}/{len(codes)}] {code} {name}: 新闻 {len(news)} → 事件 "
            f"{sum(1 for r in records if r['code'] == code)}")
        time.sleep(throttle)
    return pd.DataFrame(records)


def _winrate_line(s: pd.Series) -> str:
    s = s.dropna()
    if s.empty:
        return "n=0"
    win = (s > WIN_THRESHOLD_PCT).sum()
    up = (s > 0).sum()
    return (f"n={len(s):>4}  次日均{s.mean():+6.2f}%  中位{s.median():+6.2f}%  "
            f"上涨率(>0){up/len(s):5.0%}  胜率(>+1%){win/len(s):5.0%}")


def analyze(df: pd.DataFrame, bench_events: pd.DataFrame | None) -> None:
    if df.empty:
        log("无事件, 无法分析")
        return
    log("=" * 92)
    log(f"总事件 {len(df)}  覆盖 {df['code'].nunique()} 只  "
        f"区间 {df['trigger_day'].min()} ~ {df['trigger_day'].max()}")
    log(f"WIN 定义: 次日 close(T+1)/close(T)-1 > +{WIN_THRESHOLD_PCT}%")
    log("-" * 92)
    log(f"[全样本]           {_winrate_line(df['ret_pct'])}")

    log("\n[按情绪分组]")
    for k in ("pos", "neg", "mixed", "neutral"):
        sub = df[df["sentiment"] == k]
        log(f"  {k:<8}       {_winrate_line(sub['ret_pct'])}")

    log("\n[标题含代码/名 vs 仅正文提及]")
    for lbl, mask in (("标题命中", df["title_hit"]), ("仅正文", ~df["title_hit"])):
        log(f"  {lbl:<10}   {_winrate_line(df[mask]['ret_pct'])}")

    log("\n[当日消息面热度 (触发日新闻条数)]")
    bins = [("1条", df["day_news_count"] == 1),
            ("2-3条", df["day_news_count"].between(2, 3)),
            ("4-6条", df["day_news_count"].between(4, 6)),
            ("7条+", df["day_news_count"] >= 7)]
    for lbl, mask in bins:
        log(f"  {lbl:<8}     {_winrate_line(df[mask]['ret_pct'])}")

    log("\n[利好 + 标题命中 (组合)]")
    combo = df[(df["sentiment"] == "pos") & (df["title_hit"])]
    log(f"  pos&标题命中  {_winrate_line(combo['ret_pct'])}")

    log("\n[Top 媒体来源 (样本≥5)]")
    for media, sub in df.groupby("media"):
        if len(sub) >= 5:
            log(f"  {media[:14]:<14} {_winrate_line(sub['ret_pct'])}")

    if bench_events is not None and not bench_events.empty:
        log("\n[基准: 沪深300 同触发日次日收益]")
        merged = df.merge(bench_events, on="trigger_day", how="left",
                          suffixes=("", "_bench"))
        b = merged["ret_pct_bench"].dropna()
        if len(b):
            log(f"  沪深300        n={len(b):>4}  次日均{b.mean():+6.2f}%  "
                f"上涨率{ (b>0).mean():5.0%}")
            excess = (merged["ret_pct"] - merged["ret_pct_bench"]).dropna()
            log(f"  个股-基准 超额  均{excess.mean():+6.2f}%  "
                f"跑赢率{(excess>0).mean():5.0%}")
    log("=" * 92)


def bench_next_day_table(start: str, end: str) -> pd.DataFrame:
    """沪深300 每个交易日的次日收益, 用于基准对比。"""
    dated = fetch_kline_dated("000300", index=True)
    if not dated:
        return pd.DataFrame()
    rows = []
    for i in range(len(dated) - 1):
        d = dated[i]["date"]
        if d < start or d > end:
            continue
        t_close = dated[i]["close"]
        ret = (dated[i + 1]["close"] / t_close - 1) * 100 if t_close else None
        rows.append({"trigger_day": d, "ret_pct": round(ret, 3) if ret else None})
    return pd.DataFrame(rows)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--codes", default="", help="逗号分隔股票代码 (回退/直接指定)")
    ap.add_argument("--universe", default="codes",
                    choices=["codes", "state-db", "csv"],
                    help="标的池来源 (默认 codes; state-db=chip-scanner Mid/High)")
    default_end = date.today().isoformat()
    default_start = (date.today() - timedelta(days=180)).isoformat()
    ap.add_argument("--start", default=default_start, help="起始日 YYYY-MM-DD")
    ap.add_argument("--end", default=default_end, help="结束日 YYYY-MM-DD")
    ap.add_argument("--throttle", type=float, default=0.5, help="请求间隔秒")
    ap.add_argument("--max-pages", type=int, default=20, help="每股新闻最大翻页")
    ap.add_argument("--out", default="", help="事件明细 CSV 输出路径")
    args = ap.parse_args()

    codes = load_universe(args.universe, args.codes)
    log(f"标的池 {len(codes)} 只 | 区间 {args.start} ~ {args.end} | "
        f"来源 {args.universe if not args.codes else 'codes'}")

    df = build_events(codes, args.start, args.end, args.throttle, args.max_pages)
    if df.empty:
        log("无事件生成 (可能新闻为空或区间无 T+1)。")
        return

    bench = bench_next_day_table(args.start, args.end)
    analyze(df, bench)

    os.makedirs(OUTPUT_DIR, exist_ok=True)
    out = args.out or os.path.join(
        OUTPUT_DIR, f"news_nextday_{args.start.replace('-','')}_"
        f"{args.end.replace('-','')}.csv")
    df.sort_values(["code", "trigger_day"]).to_csv(
        out, index=False, encoding="utf-8-sig")
    log(f"[output] 事件明细 → {out}")


if __name__ == "__main__":
    main()
