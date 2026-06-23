"""
L1 抓取层 — 东方财富全 A 股快照(可控节流版)。

策略(避免被 ban IP):
  - 直接打 push2 API,自己翻页,每页之间 sleep 2-4s
  - 多 host 轮换; 单 host 断连时快速切换, 避免整轮超时
  - 总 page < 60(每页 100 只 → 5500+ 全 A)
  - 单次完整跑预计 4-6 分钟
  - 每页 UA 轮换,带 Referer

用法:
  python tools/scanner/fetch_eastmoney.py [--out PATH] [--quiet] [--sleep 4]

依赖: 标准库 urllib + json,无需 akshare/playwright。
"""
import json
import sys
import io
import os
import time
import random
import argparse
import urllib.request
import urllib.error
from datetime import datetime, timezone, timedelta

if hasattr(sys.stdout, "buffer"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")


# 东财 push2 API 字段映射(f 编号 → 标准字段)
# 参考 https://push2.eastmoney.com/api/qt/clist/get
FIELD_MAP = {
    "f12": "code",
    "f14": "name",
    "f2":  "price",            # 最新价
    "f3":  "change_pct",       # 涨跌幅 %
    "f4":  "change_amount",    # 涨跌额
    "f5":  "volume_lots",      # 成交量(手)
    "f6":  "turnover_yuan",    # 成交额(元)
    "f7":  "amplitude_pct",    # 振幅
    "f15": "high_today",
    "f16": "low_today",
    "f17": "open_today",
    "f18": "prev_close",
    "f10": "volume_ratio",     # 量比
    "f8":  "turnover_rate_pct",
    "f9":  "pe_ttm",
    "f23": "pb",
    "f20": "market_cap",
    "f21": "float_market_cap",
    "f22": "change_speed",
    "f11": "change_5min_pct",
    "f24": "change_60d_pct",
    "f25": "change_ytd_pct",
    "f26": "list_date",        # 上市日 YYYYMMDD
    "f100": "industry",        # 所属行业
    "f62": "main_net_inflow",   # 主力净流入(元)
    "f184": "main_net_pct",     # 主力净占比 %
    "f66": "super_net_inflow",  # 超大单净流入(元)
    "f69": "super_net_pct",     # 超大单净占比 %
    "f72": "large_net_inflow",  # 大单净流入(元)
    "f75": "large_net_pct",     # 大单净占比 %
}

FIELD_PARAM = ",".join(FIELD_MAP.keys())

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:120.0) Gecko/20100101 Firefox/120.0",
]

PUSH2_HOSTS = [
    "https://48.push2.eastmoney.com",
    "https://push2.eastmoney.com",
    "https://76.push2.eastmoney.com",
    "https://82.push2.eastmoney.com",
]


def detect_exchange(code: str) -> str:
    if code.startswith("6"):
        return "SS"
    if code.startswith(("0", "3")):
        return "SZ"
    if code.startswith(("4", "8", "9")):
        return "BJ"
    return "?"


def build_url(page: int, page_size: int = 100, host: str | None = None) -> str:
    # fs=m:0+t:6,m:0+t:80,m:1+t:2,m:1+t:23  →  沪深 A 股(主板+中小板+创业板+科创板)
    host = host or PUSH2_HOSTS[0]
    return (
        f"{host}/api/qt/clist/get?"
        f"pn={page}&pz={page_size}&po=1&np=1&ut=bd1d9ddb04089700cf9c27f6f7426281"
        f"&fltt=2&invt=2&dect=1"
        f"&fs=m:0+t:6,m:0+t:80,m:1+t:2,m:1+t:23,m:0+t:81+s:2048"
        f"&fields={FIELD_PARAM}"
        f"&_={int(time.time() * 1000)}"
    )


def fetch_page(page: int, attempt: int = 0, verbose: bool = True,
               page_size: int = 100) -> tuple[list[dict] | None, int]:
    """
    返回 (rows, total_count)。失败返回 (None, 0)。
    """
    host = PUSH2_HOSTS[(page + attempt - 1) % len(PUSH2_HOSTS)]
    url = build_url(page, page_size=page_size, host=host)
    ua = random.choice(USER_AGENTS)
    req = urllib.request.Request(url, headers={
        "User-Agent": ua,
        "Referer": "https://quote.eastmoney.com/center/gridlist.html",
        "Accept": "*/*",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    })
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            raw = r.read().decode("utf-8", errors="ignore")
        data = json.loads(raw)
        if not data or "data" not in data or not data["data"]:
            return [], 0
        d = data["data"]
        diff = d.get("diff") or []
        total = d.get("total", 0)
        rows = []
        for item in diff:
            row = {}
            for f, std in FIELD_MAP.items():
                v = item.get(f)
                if v == "-" or v is None:
                    row[std] = None
                else:
                    if std in ("code", "name", "industry"):
                        row[std] = str(v) if v is not None else None
                    elif std == "list_date":
                        try:
                            row[std] = int(v)
                        except (TypeError, ValueError):
                            row[std] = None
                    else:
                        try:
                            row[std] = float(v)
                        except (TypeError, ValueError):
                            row[std] = None
            row["exchange"] = detect_exchange(row.get("code", "") or "")
            rows.append(row)
        return rows, total
    except Exception as e:
        if verbose:
            print(f"[fetch] 页 {page} 第 {attempt+1} 次失败({host}): {type(e).__name__}: {e}", flush=True)
        return None, 0


def fetch_all(sleep_sec: float = 4.0, page_size: int = 100, max_pages: int = 60,
              verbose: bool = True) -> tuple[list[dict], dict]:
    """
    全市场抓取。每页间 sleep,失败退避。
    """
    all_rows: list[dict] = []
    total_count = 0
    failed_pages: list[int] = []
    t0 = time.time()

    page = 1
    while page <= max_pages:
        rows = None
        for attempt in range(6):
            rows, total = fetch_page(page, attempt=attempt, verbose=verbose,
                                     page_size=page_size)
            if rows is not None:
                if total_count == 0 and total > 0:
                    total_count = total
                break
            # 退避
            backoff = [5, 10, 20, 30, 45, 60][attempt]
            if verbose:
                print(f"[fetch] 退避 {backoff}s 后重试", flush=True)
            time.sleep(backoff)

        if rows is None:
            failed_pages.append(page)
            if verbose:
                print(f"[fetch] 页 {page} 多 host 重试失败,跳过", flush=True)
        else:
            all_rows.extend(rows)
            if verbose:
                # 进度估算
                if total_count > 0:
                    pct = 100 * len(all_rows) / total_count
                    print(f"[fetch] 页 {page} OK,累计 {len(all_rows)}/{total_count} ({pct:.0f}%)", flush=True)
                else:
                    print(f"[fetch] 页 {page} OK,累计 {len(all_rows)} 只", flush=True)

            # 提前停:若返回少于 page_size,说明到末页
            if len(rows) < page_size:
                if verbose:
                    print(f"[fetch] 页 {page} 返回 {len(rows)} < {page_size},末页,停止", flush=True)
                break

        page += 1

        # 节流 sleep — 加随机抖动 ±20% 避免规律性
        jitter = sleep_sec * random.uniform(0.8, 1.2)
        time.sleep(jitter)

    elapsed = time.time() - t0
    if verbose:
        print(f"[fetch] 完成 {len(all_rows)}/{total_count} 只,{elapsed:.1f}s,失败页 {failed_pages}", flush=True)

    return all_rows, {
        "fetch_duration_sec": round(elapsed, 1),
        "total_market": total_count,
        "fetched_count": len(all_rows),
        "failed_pages": failed_pages,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default=None)
    parser.add_argument("--quiet", action="store_true")
    parser.add_argument("--sleep", type=float, default=4.0,
                        help="页间 sleep 秒(默认 4,被 ban 时调大到 6-8)")
    parser.add_argument("--max-pages", type=int, default=60)
    args = parser.parse_args()

    bjt = timezone(timedelta(hours=8))
    now = datetime.now(bjt)
    today = now.strftime("%Y-%m-%d")

    if args.out is None:
        out_dir = os.path.join(os.path.dirname(__file__), "..", "..", "data", "scanner")
        os.makedirs(out_dir, exist_ok=True)
        args.out = os.path.join(out_dir, f"raw-{today}.json")

    print(f"[start] 节流 sleep={args.sleep}s/页,预计 4-6 分钟", flush=True)

    stocks, meta = fetch_all(
        sleep_sec=args.sleep,
        max_pages=args.max_pages,
        verbose=not args.quiet,
    )

    payload = {
        "metadata": {
            "fetched_at": now.strftime("%Y-%m-%d %H:%M:%S BJT"),
            "source": "eastmoney_push2_clist (throttled)",
            "total_count": len(stocks),
            **meta,
            "fields_explained": {
                "price": "现价 ¥",
                "market_cap": "总市值(元)",
                "pe_ttm": "PE-动态(亏损为负)",
                "change_60d_pct": "60 日涨幅 %",
                "change_ytd_pct": "年初至今涨幅 %(52w 涨幅近似代理)",
            },
        },
        "stocks": stocks,
    }

    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, separators=(",", ":"))

    print(f"[done] {len(stocks)} 只 → {args.out}", flush=True)


if __name__ == "__main__":
    main()
