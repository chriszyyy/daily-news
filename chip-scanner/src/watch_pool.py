"""观察池晋升逻辑 (Mid → High) — 基于筹码指标筛"低位单峰套牢盘"。

输入: universe CSV (基础过滤后) + 筹码指标。
"低位单峰套牢盘" 三要素量化:
  - 单峰(密集)  : SCR (90集中度) 越小越密集
  - 套牢          : 获利比例低 (多数持仓被套, 抛压小, 惜售)
  - 低位          : 现价 <= 平均成本 (价在密集峰下沿/下方)

两级门槛:
  Mid  (观察池) : SCR < 0.15  且 获利比例 < 0.40  且 现价 <= 平均成本*1.05
  High (临界池) : SCR < 0.10  且 获利比例 < 0.25  且 现价 <= 平均成本
                  (High 直接送视觉终审, 目标 <= 20 只)

用法:
  python src/watch_pool.py [--limit N] [--throttle 0.4]
"""

from __future__ import annotations

import argparse
import json
import os
import time
from datetime import datetime

import pandas as pd

import chip_calc

# ---- 晋升门槛 (集中配置) ----
MID_SCR = 0.15
MID_PROFIT = 0.40
MID_PRICE_MULT = 1.05   # 现价 <= 平均成本 * 1.05 (允许略高于成本)

HIGH_SCR = 0.10
HIGH_PROFIT = 0.25
HIGH_PRICE_MULT = 1.00

OUTPUT_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "output")
CACHE_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "chips")


def cache_path() -> str:
    ts = datetime.now().strftime("%Y%m%d")
    os.makedirs(CACHE_DIR, exist_ok=True)
    return os.path.join(CACHE_DIR, f"chips_{ts}.jsonl")


def load_cache(path: str) -> dict[str, dict]:
    """读取已抓筹码缓存 (jsonl, 每行一只)。"""
    cache: dict[str, dict] = {}
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    r = json.loads(line)
                    cache[r["code"]] = r
                except (json.JSONDecodeError, KeyError):
                    continue
    return cache


def append_cache(path: str, rec: dict) -> None:
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")


def latest_universe() -> str:
    files = sorted(f for f in os.listdir(OUTPUT_DIR)
                   if f.startswith("universe_") and f.endswith(".csv"))
    if not files:
        raise FileNotFoundError("未找到 universe_*.csv, 先跑 universe_filter.py")
    return os.path.join(OUTPUT_DIR, files[-1])


def classify(row) -> str:
    """返回 High / Mid / 未达标。"""
    scr, profit, price, avg = (row["SCR"], row["获利比例"],
                               row["price"], row["平均成本"])
    if any(pd.isna(x) for x in (scr, profit, price, avg)) or avg <= 0:
        return "未达标"
    if scr < HIGH_SCR and profit < HIGH_PROFIT and price <= avg * HIGH_PRICE_MULT:
        return "High"
    if scr < MID_SCR and profit < MID_PROFIT and price <= avg * MID_PRICE_MULT:
        return "Mid"
    return "未达标"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=0,
                    help="只处理前 N 只 (PoC 用, 0=全部)")
    ap.add_argument("--throttle", type=float, default=0.4)
    args = ap.parse_args()

    uni_path = latest_universe()
    uni = pd.read_csv(uni_path, dtype={"code": str})
    uni["code"] = uni["code"].str.zfill(6)
    if args.limit:
        uni = uni.head(args.limit)
    print(f"[watch] 候选 {len(uni)} 只 (来自 {os.path.basename(uni_path)})")

    cpath = cache_path()
    cache = load_cache(cpath)
    print(f"[cache] 已有 {len(cache)} 只缓存 ({os.path.basename(cpath)})")

    def scan(codes: list[str], throttle: float) -> list[str]:
        """抓取并即时落盘缓存; 返回本轮失败 code 列表。"""
        fails = []
        cur = throttle
        streak_fail = 0
        for i, code in enumerate(codes, 1):
            if code in cache:           # 断点续抓: 跳过已缓存
                continue
            m = chip_calc.fetch_chip_latest(code)
            if m is None:
                fails.append(code)
                streak_fail += 1
                if streak_fail >= 5:    # 疑似限流, 冷却
                    cur = min(cur * 1.5, 2.0)
                    print(f"[chip] 连续失败, 节流升至 {cur:.2f}s, 冷却 20s",
                          flush=True)
                    time.sleep(20)
                    streak_fail = 0
            else:
                cache[code] = m
                append_cache(cpath, m)   # 即时落盘, 永不丢
                streak_fail = 0
                cur = max(cur * 0.95, throttle)
            if i % 100 == 0:
                print(f"[chip] {i}/{len(codes)}, 缓存 {len(cache)}, "
                      f"本轮失败 {len(fails)}, 节流 {cur:.2f}s", flush=True)
            time.sleep(cur)
        return fails

    codes = uni["code"].tolist()
    fails = scan(codes, args.throttle)

    # 失败重试一轮 (限流恢复后)
    if fails:
        print(f"[chip] 重试 {len(fails)} 只失败项, 冷却 30s ...", flush=True)
        time.sleep(30)
        fails = scan(fails, max(args.throttle * 2, 0.4))

    rows = [cache[c] for c in codes if c in cache]
    print(f"[chip] 完成 {len(rows)}/{len(codes)}, 未获取 {len(codes) - len(rows)}",
          flush=True)
    chips = pd.DataFrame(rows)
    if chips.empty:
        print("[watch] 筹码数据为空, 终止")
        return

    merged = uni.merge(chips, on="code", how="inner")
    merged["level"] = merged.apply(classify, axis=1)
    merged["套牢比例"] = (1 - merged["获利比例"]).round(3)

    dist = merged["level"].value_counts().to_dict()
    print(f"\n==== 晋升结果 ==== {dist}")

    ts = datetime.now().strftime("%Y%m%d")
    cols = ["code", "name", "price", "平均成本", "SCR", "获利比例", "套牢比例",
            "90成本低", "90成本高", "level", "成交额占流通比%", "健康度",
            "高位标记", "industry"]
    cols = [c for c in cols if c in merged.columns]

    high = merged[merged["level"] == "High"].sort_values("SCR")
    mid = merged[merged["level"] == "Mid"].sort_values("SCR")

    high_path = os.path.join(OUTPUT_DIR, f"high_pool_{ts}.csv")
    mid_path = os.path.join(OUTPUT_DIR, f"mid_pool_{ts}.csv")
    high[cols].to_csv(high_path, index=False, encoding="utf-8-sig")
    mid[cols].to_csv(mid_path, index=False, encoding="utf-8-sig")

    print(f"[output] High {len(high)} 只 → {high_path}")
    print(f"[output] Mid  {len(mid)} 只 → {mid_path}")
    if not high.empty:
        print("\nHigh 池预览 (送视觉终审):")
        print(high[["code", "name", "price", "平均成本", "SCR",
                    "套牢比例"]].head(20).to_string(index=False))


if __name__ == "__main__":
    main()
