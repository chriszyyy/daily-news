"""筹码"单峰密集"策略回测。

方法 (严防未来函数):
  - 对历史信号日 T, 仅用 T 及之前的 K 线算筹码指标 → 选 Top-N。
  - 再看 T 之后 5/10/20 个交易日的真实涨跌, 统计胜率/平均收益/对比基准。

数据: 腾讯日 K (带日期), 一次拉长历史, 本地按日期切片 (避免重复请求)。

用法:
  python src/backtest.py --signal-date 2026-05-16 --topn 20 --throttle 0.2
  python src/backtest.py --signal-date 2026-05-16,2026-05-09 --topn 20
"""

from __future__ import annotations

import argparse
import os
import random
import sys
import time
from datetime import date, datetime

import numpy as np
import pandas as pd
import requests

# 强制 UTF-8 输出
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:  # noqa: BLE001
        pass

_LOG_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "output")
_LOG_PATH = os.path.join(_LOG_DIR, "backtest_run.log")


def log(msg: str) -> None:
    """同时打印 + 写 UTF-8 文件 (不依赖 shell 重定向)。"""
    line = f"{datetime.now():%H:%M:%S} {msg}"
    try:
        print(line, flush=True)
    except Exception:  # noqa: BLE001
        pass
    with open(_LOG_PATH, "a", encoding="utf-8") as f:
        f.write(line + "\n")

import chip_calc as cc

OUTPUT_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "output")
HOLD_DAYS = (5, 10, 20)
RECENT_PRESET_DATES = (
    "2026-04-01", "2026-04-15", "2026-04-29",
    "2026-05-09", "2026-05-16", "2026-05-23",
)

# 复用 chip_calc 的策略阈值 (从 orchestrator 同步, 避免漂移)
SECOND_MAX = 0.50
BAND70_MAX = 0.09
POS_MIN = -0.05


def fetch_kline_dated(code: str, lmt: int = 400, max_retries: int = 3,
                      index: bool = False) -> list[dict] | None:
    """拉带日期的日 K (旧→新)。返回 [{date,close,high,low,tr}, ...]。

    index=True 时 code 为指数 (沪深300=000300 → sh000300)。
    """
    if index:
        sym = f"sh{code}" if code.startswith(("000", "999")) else f"sz{code}"
    else:
        sym = cc._tx_symbol(code)
    start = date.today().replace(year=date.today().year - 2).isoformat()
    params = {"param": f"{sym},day,{start},2050-12-31,{lmt},"}
    for attempt in range(max_retries):
        try:
            r = requests.get(cc.TX_URL, params=params,
                             headers={"User-Agent": random.choice(cc.UA)},
                             timeout=10)
            r.raise_for_status()
            node = (r.json().get("data") or {}).get(sym) or {}
            rows = node.get("day") or node.get("qfqday")
            if not rows:
                return None
            out = []
            for p in rows:
                try:
                    tr = float(p[7]) if len(p) > 7 and p[7] not in ("", None) else 0.0
                except (ValueError, TypeError):
                    tr = 0.0
                out.append({"date": p[0], "close": float(p[2]),
                            "high": float(p[3]), "low": float(p[4]), "tr": tr})
            return out
        except Exception:  # noqa: BLE001
            time.sleep(0.6 * (attempt + 1))
    return None


def metrics_asof(dated: list[dict], asof: str) -> dict | None:
    """用 asof(含)之前的 K 线算筹码指标。返回含 band70/次峰比/距主峰 的 dict。"""
    sub = [d for d in dated if d["date"] <= asof]
    if len(sub) < 60:
        return None
    sub = sub[-cc.KLINE_DAYS:]
    kline = [[d["close"], d["high"], d["low"], d["tr"]] for d in sub]
    return cc.compute_chips(kline)


def momentum_asof(dated: list[dict], asof: str) -> dict | None:
    """启动型量价信号 (仅用 asof 及之前数据, 防未来函数)。"""
    sub = [d for d in dated if d["date"] <= asof]
    if len(sub) < 60:
        return None
    closes = np.array([d["close"] for d in sub], dtype=float)
    highs = np.array([d["high"] for d in sub], dtype=float)
    trs = np.array([d["tr"] for d in sub], dtype=float)
    cur = closes[-1]

    ma5 = float(np.mean(closes[-5:]))
    ma10 = float(np.mean(closes[-10:]))
    ma20 = float(np.mean(closes[-20:]))
    ma60 = float(np.mean(closes[-60:]))

    vol_ratio = (float(np.mean(trs[-5:])) / float(np.mean(trs[-25:-5]))
                 if np.mean(trs[-25:-5]) > 0 else None)
    mom5 = (cur / closes[-6] - 1) * 100 if closes[-6] > 0 else None
    mom20 = (cur / closes[-21] - 1) * 100 if len(closes) >= 21 and closes[-21] > 0 else None
    # 突破: 现价创近20日新高 (不含今天)
    breakout20 = cur >= highs[-21:-1].max() if len(highs) >= 21 else False
    # 均线多头: MA5>MA10>MA20
    ma_bull = ma5 > ma10 > ma20
    # 站上 MA20
    above_ma20 = cur > ma20

    return {
        "现价": round(cur, 2), "MA20": round(ma20, 2), "MA60": round(ma60, 2),
        "放量比": round(vol_ratio, 3) if vol_ratio else None,
        "近5日涨幅": round(mom5, 2) if mom5 is not None else None,
        "近20日涨幅": round(mom20, 2) if mom20 is not None else None,
        "突破20日新高": bool(breakout20),
        "均线多头": bool(ma_bull),
        "站上MA20": bool(above_ma20),
    }


def forward_returns(dated: list[dict], asof: str) -> dict:
    """asof 之后 N 日收益 (%)。基准价=asof 收盘。"""
    idx = next((i for i, d in enumerate(dated) if d["date"] == asof), None)
    if idx is None:
        # 取 <= asof 的最后一根
        prior = [i for i, d in enumerate(dated) if d["date"] <= asof]
        if not prior:
            return {}
        idx = prior[-1]
    base = dated[idx]["close"]
    out = {}
    for n in HOLD_DAYS:
        j = idx + n
        out[n] = round((dated[j]["close"] / base - 1) * 100, 2) if j < len(dated) and base > 0 else None
    return out


def load_candidates() -> list[tuple[str, str]]:
    """候选池 = 最新 universe (已过 基础硬过滤 + 盈利)。返回 [(code,name)]。"""
    files = sorted(f for f in os.listdir(OUTPUT_DIR)
                   if f.startswith("universe_") and f.endswith(".csv"))
    if not files:
        raise FileNotFoundError("无 universe CSV")
    df = pd.read_csv(os.path.join(OUTPUT_DIR, files[-1]), dtype={"code": str})
    df["code"] = df["code"].str.zfill(6)
    return list(zip(df["code"], df["name"]))


def run_one(signal_date: str, topn: int, throttle: float,
            limit: int = 0) -> pd.DataFrame:
    cands = load_candidates()
    if limit:
        cands = cands[:limit]
    log(f"[bt] 信号日 {signal_date}: 扫描 {len(cands)} 候选 ...")

    # 基准: 沪深300
    bench = fetch_kline_dated("000300", index=True)
    bench_fwd = forward_returns(bench, signal_date) if bench else {}

    # 收集所有"单峰密集"基础命中 + 全指标 + 未来收益 (增量落盘, 防中断丢数据)
    raw_csv = os.path.join(OUTPUT_DIR, f"backtest_raw_{signal_date.replace('-','')}.csv")
    done_codes = set()
    if os.path.exists(raw_csv):  # 断点续跑
        try:
            prev = pd.read_csv(raw_csv, dtype={"code": str})
            prev["code"] = prev["code"].str.zfill(6)
            done_codes = set(prev["code"])
            log(f"[bt] 续跑: 已有 {len(done_codes)} 只命中缓存")
        except Exception:  # noqa: BLE001
            pass

    import csv as _csv
    cols = (["code", "name", "带宽70", "次峰比", "距主峰", "放量比", "近5日涨幅"]
            + [f"+{n}日%" for n in HOLD_DAYS])
    write_header = not os.path.exists(raw_csv)
    rows = []
    for i, (code, name) in enumerate(cands, 1):
        if code in done_codes:
            continue
        dated = fetch_kline_dated(code)
        if dated:
            m = metrics_asof(dated, signal_date)
            if m and m["带宽70"] is not None and m["次峰比"] is not None \
                    and m["距主峰"] is not None:
                if (m["次峰比"] <= SECOND_MAX and m["带宽70"] <= BAND70_MAX
                        and m["距主峰"] >= POS_MIN):
                    fwd = forward_returns(dated, signal_date)
                    rec = {"code": code, "name": name,
                           "带宽70": m["带宽70"], "次峰比": m["次峰比"],
                           "距主峰": m["距主峰"], "放量比": m.get("放量比"),
                           "近5日涨幅": m.get("近5日涨幅"),
                           **{f"+{n}日%": fwd.get(n) for n in HOLD_DAYS}}
                    rows.append(rec)
                    # 即时追加落盘
                    with open(raw_csv, "a", newline="", encoding="utf-8-sig") as f:
                        w = _csv.DictWriter(f, fieldnames=cols)
                        if write_header:
                            w.writeheader()
                            write_header = False
                        w.writerow(rec)
        if i % 200 == 0:
            log(f"[bt]   {i}/{len(cands)}, 本轮命中 {len(rows)}")
        time.sleep(throttle)

    # 合并历史缓存 + 本轮
    if os.path.exists(raw_csv):
        df = pd.read_csv(raw_csv, dtype={"code": str})
        df["code"] = df["code"].str.zfill(6)
    else:
        df = pd.DataFrame(rows)
    if df.empty:
        log("[bt] 无命中")
        return df
    df["信号日"] = signal_date

    # ---- 策略变体对比 ----
    def stats(sub: pd.DataFrame, label: str):
        sub = sub.sort_values("带宽70").head(topn)
        log(f"  [{label}] 选 {len(sub)} 只:")
        for n in HOLD_DAYS:
            s = sub[f"+{n}日%"].dropna()
            if len(s):
                win = (s > 0).sum()
                bn = bench_fwd.get(n)
                ex = f"{s.mean() - bn:+.2f}%" if isinstance(bn, (int, float)) else "—"
                log(f"    {n:>2}日: 均 {s.mean():+.2f}% 胜率 {win}/{len(s)}="
                    f"{win/len(s):.0%} 超额 {ex}")

    log(f"==== 信号日 {signal_date} 策略对比 ====")
    log("基准沪深300: " + " / ".join(
        f"+{n}日 {bench_fwd.get(n)}%" for n in HOLD_DAYS))
    stats(df, "A 纯密集 (原策略)")
    stats(df[df["距主峰"] > 0], "B 密集+站上主峰")
    stats(df[(df["放量比"].fillna(0) > 1.2)], "C 密集+放量")
    stats(df[(df["距主峰"] > 0) & (df["放量比"].fillna(0) > 1.2)],
          "D 密集+站上主峰+放量(突破)")
    stats(df[(df["近5日涨幅"].fillna(-99) > 0) & (df["放量比"].fillna(0) > 1.2)],
          "E 密集+近5日涨+放量")
    return df


def run_momentum(signal_date: str, topn: int, throttle: float,
                 limit: int = 0) -> pd.DataFrame:
    """启动型量价策略回测 (不依赖筹码密集)。增量落盘+断点续跑。"""
    import csv as _csv
    cands = load_candidates()
    if limit:
        cands = cands[:limit]
    log(f"[mom] 信号日 {signal_date}: 扫描 {len(cands)} 候选 ...")

    bench = fetch_kline_dated("000300", index=True)
    bench_fwd = forward_returns(bench, signal_date) if bench else {}

    raw_csv = os.path.join(OUTPUT_DIR, f"mom_raw_{signal_date.replace('-','')}.csv")
    done = set()
    if os.path.exists(raw_csv):
        try:
            prev = pd.read_csv(raw_csv, dtype={"code": str})
            prev["code"] = prev["code"].str.zfill(6)
            done = set(prev["code"])
            log(f"[mom] 续跑: 已有 {len(done)} 只缓存")
        except Exception:  # noqa: BLE001
            pass

    cols = (["code", "name", "放量比", "近5日涨幅", "近20日涨幅",
             "突破20日新高", "均线多头", "站上MA20"]
            + [f"+{n}日%" for n in HOLD_DAYS])
    write_header = not os.path.exists(raw_csv)
    cnt = 0
    for i, (code, name) in enumerate(cands, 1):
        if code in done:
            continue
        dated = fetch_kline_dated(code)
        if dated:
            m = momentum_asof(dated, signal_date)
            if m:
                fwd = forward_returns(dated, signal_date)
                rec = {"code": code, "name": name,
                       "放量比": m["放量比"], "近5日涨幅": m["近5日涨幅"],
                       "近20日涨幅": m["近20日涨幅"],
                       "突破20日新高": m["突破20日新高"],
                       "均线多头": m["均线多头"], "站上MA20": m["站上MA20"],
                       **{f"+{n}日%": fwd.get(n) for n in HOLD_DAYS}}
                with open(raw_csv, "a", newline="", encoding="utf-8-sig") as f:
                    w = _csv.DictWriter(f, fieldnames=cols)
                    if write_header:
                        w.writeheader()
                        write_header = False
                    w.writerow(rec)
                cnt += 1
        if i % 200 == 0:
            log(f"[mom]   {i}/{len(cands)}, 已记录 {cnt}")
        time.sleep(throttle)

    df = pd.read_csv(raw_csv, dtype={"code": str})
    df["code"] = df["code"].str.zfill(6)
    df["信号日"] = signal_date
    for c in ("放量比", "近5日涨幅", "近20日涨幅"):
        df[c] = pd.to_numeric(df[c], errors="coerce")

    def stats(sub: pd.DataFrame, label: str, sortcol: str):
        sub = sub.sort_values(sortcol, ascending=False).head(topn)
        log(f"  [{label}] 选 {len(sub)} 只:")
        for n in HOLD_DAYS:
            s = pd.to_numeric(sub[f"+{n}日%"], errors="coerce").dropna()
            if len(s):
                win = (s > 0).sum()
                bn = bench_fwd.get(n)
                ex = f"{s.mean() - bn:+.2f}%" if isinstance(bn, (int, float)) else "—"
                log(f"    {n:>2}日: 均 {s.mean():+.2f}% 胜率 {win}/{len(s)}="
                    f"{win/len(s):.0%} 超额 {ex}")

    log(f"==== 信号日 {signal_date} 启动型策略对比 ====")
    log("基准沪深300: " + " / ".join(
        f"+{n}日 {bench_fwd.get(n)}%" for n in HOLD_DAYS))
    # 量价启动变体 (排序取 Top-N)
    stats(df[(df["放量比"] > 1.5) & (df["近5日涨幅"] > 3)],
          "M1 放量+近5日涨>3%", "放量比")
    stats(df[df["突破20日新高"] == True],  # noqa: E712
          "M2 突破20日新高", "放量比")
    stats(df[(df["突破20日新高"] == True) & (df["放量比"] > 1.5)],  # noqa: E712
          "M3 放量突破新高", "放量比")
    stats(df[(df["均线多头"] == True) & (df["放量比"] > 1.5)],  # noqa: E712
          "M4 均线多头+放量", "近5日涨幅")
    stats(df[(df["站上MA20"] == True) & (df["放量比"] > 1.5)  # noqa: E712
             & (df["近20日涨幅"] < 30) & (df["近5日涨幅"] > 2)],
          "M5 启动(站上MA20+放量+涨+不追高)", "放量比")
    return df


def summarize_trend_batch(dates: list[str], throttle: float, limit: int = 0) -> None:
    """多日期趋势条件验证。只使用信号日前 K 线, 不用当天之后信息。"""
    frames = []
    for sd in dates:
        df = run_momentum(sd, topn=99999, throttle=throttle, limit=limit)
        if not df.empty:
            df["信号日"] = sd
            frames.append(df)
    if not frames:
        log("[trend-batch] 无样本")
        return
    df = pd.concat(frames, ignore_index=True)
    for c in ("放量比", "近5日涨幅", "近20日涨幅"):
        df[c] = pd.to_numeric(df[c], errors="coerce")
    for c in ("突破20日新高", "均线多头", "站上MA20"):
        df[c] = df[c].astype(str).str.lower().isin(("true", "1", "是"))

    tests = {
        "T1 站上MA20": df["站上MA20"],
        "T2 新高": df["突破20日新高"],
        "T3 新高+5日涨>=8": df["突破20日新高"] & (df["近5日涨幅"] >= 8),
        "T4 站上MA20+5日涨8~25": (
            df["站上MA20"] & (df["近5日涨幅"] >= 8) & (df["近5日涨幅"] <= 25)
        ),
        "T5 过热(5日>35或20日>100)": (
            (df["近5日涨幅"] > 35) | (df["近20日涨幅"] > 100)
        ),
    }
    log("==== 趋势条件多日期汇总 ====")
    for label, mask in tests.items():
        sub = df[mask]
        log(f"[{label}] n={len(sub)}")
        for n in HOLD_DAYS:
            s = pd.to_numeric(sub[f"+{n}日%"], errors="coerce").dropna()
            if len(s):
                win = (s > 0).sum()
                log(f"  +{n}日: 均{s.mean():+.2f}% 中位{s.median():+.2f}% "
                    f"胜率{win}/{len(s)}={win/len(s):.0%} "
                    f"P25{s.quantile(.25):+.2f}% P75{s.quantile(.75):+.2f}%")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--signal-date", default="",
                    help="信号日, 逗号分隔多个 (YYYY-MM-DD)")
    ap.add_argument("--preset", choices=["recent"], default=None,
                    help="预设多日期样本; recent=近期 6 个信号日")
    ap.add_argument("--topn", type=int, default=20)
    ap.add_argument("--throttle", type=float, default=0.2)
    ap.add_argument("--limit", type=int, default=0, help="限制候选数(测试用)")
    ap.add_argument("--mode", default="chip", choices=["chip", "momentum", "trend-batch"],
                    help="chip=筹码密集, momentum=量价, trend-batch=多日期趋势验证")
    args = ap.parse_args()

    if args.preset == "recent":
        dates = list(RECENT_PRESET_DATES)
    else:
        dates = [sd.strip() for sd in args.signal_date.split(",") if sd.strip()]
    if not dates:
        raise SystemExit("请提供 --signal-date 或 --preset recent")
    if args.mode == "trend-batch":
        summarize_trend_batch(dates, args.throttle, args.limit)
        return

    runner = run_momentum if args.mode == "momentum" else run_one
    all_dfs = []
    for sd in dates:
        df = runner(sd, args.topn, args.throttle, args.limit)
        if not df.empty:
            df["信号日"] = sd
            all_dfs.append(df)
    if all_dfs:
        merged = pd.concat(all_dfs, ignore_index=True)
        ts = "_".join(d.replace("-", "") for d in dates)
        out = os.path.join(OUTPUT_DIR, f"backtest_{ts}.csv")
        merged.to_csv(out, index=False, encoding="utf-8-sig")
        log(f"[output] 明细 → {out}")
        # 全样本汇总
        log("==== 全样本汇总 ====")
        for n in HOLD_DAYS:
            col = f"+{n}日%"
            s = merged[col].dropna()
            if len(s):
                win = (s > 0).sum()
                log(f"  {n:>2}日: 平均 {s.mean():+.2f}% | "
                    f"胜率 {win}/{len(s)}={win / len(s):.0%}")


if __name__ == "__main__":
    main()
