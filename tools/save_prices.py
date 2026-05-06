"""
价格数据保存/管理工具
用法: 不直接运行。由 Claude 在 session 中调用 Yahoo Finance 后，
     将数据格式化为标准 JSON 保存到 data/prices/。

数据格式:
{
    "metadata": {
        "generated_at": "2026-05-01T15:30:00",   # 生成时间
        "period": "6mo",                           # 拉取周期
        "source": "yahoo_finance",                 # 数据来源
        "note": "..."                              # 可选备注
    },
    "stocks": {
        "600667.SS": {
            "name": "太极实业",
            "data": [
                {"date": "2025-10-30", "open": 8.80, "high": 9.13, "low": 8.73,
                 "close": 8.97, "volume": 217613783},
                ...
            ]
        },
        ...
    }
}

文件命名: data/prices/YYYY-MM-DD.json （按生成日期）
过期策略: 价格数据超过7天视为过期，需要重新拉取。

过期检查:
  python tools/save_prices.py --check
  打印每个数据文件的时效状态。
"""
import json
import os
import sys
from datetime import datetime, timedelta

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "prices")

EXPIRY_DAYS = 7  # 超过7天视为过期


def get_latest_file() -> str | None:
    """查找 data/prices/ 下最新的 JSON 文件"""
    if not os.path.exists(DATA_DIR):
        return None
    files = sorted(
        [f for f in os.listdir(DATA_DIR) if f.endswith(".json")],
        reverse=True
    )
    return os.path.join(DATA_DIR, files[0]) if files else None


def check_freshness(filepath: str) -> dict:
    """检查数据文件的时效性"""
    with open(filepath, 'r', encoding='utf-8') as f:
        data = json.load(f)

    meta = data.get("metadata", {})
    generated = meta.get("generated_at", "")
    try:
        gen_dt = datetime.fromisoformat(generated)
    except (ValueError, TypeError):
        return {"file": filepath, "status": "unknown", "message": "Cannot parse generated_at"}

    age = datetime.now() - gen_dt
    tickers = list(data.get("stocks", {}).keys())
    data_points = {t: len(data["stocks"][t].get("data", [])) for t in tickers}

    if age.days > EXPIRY_DAYS:
        status = "EXPIRED"
    elif age.days > EXPIRY_DAYS - 2:
        status = "EXPIRING_SOON"
    else:
        status = "FRESH"

    # 检查每只股票的最后数据日期
    last_dates = {}
    for t in tickers:
        entries = data["stocks"][t].get("data", [])
        if entries:
            last_dates[t] = entries[-1].get("date", "unknown")

    return {
        "file": os.path.basename(filepath),
        "generated_at": generated,
        "age_days": age.days,
        "status": status,
        "tickers": tickers,
        "data_points": data_points,
        "last_dates": last_dates,
    }


def create_price_entry(yahoo_data: list[dict], name: str) -> dict:
    """
    将 Yahoo Finance 返回的原始数据转换为标准格式。
    yahoo_data: Yahoo Finance get_historical_stock_prices 返回的列表
    """
    entries = []
    for row in yahoo_data:
        date_str = row.get("Date", "")
        # Yahoo Finance 返回 ISO 格式，截取日期部分
        if "T" in date_str:
            date_str = date_str.split("T")[0]

        entries.append({
            "date": date_str,
            "open": round(row.get("Open", 0), 2),
            "high": round(row.get("High", 0), 2),
            "low": round(row.get("Low", 0), 2),
            "close": round(row.get("Close", 0), 2),
            "volume": int(row.get("Volume", 0)),
        })

    return {
        "name": name,
        "data": entries,
    }


def main():
    """CLI: 检查数据时效"""
    if "--check" in sys.argv:
        if not os.path.exists(DATA_DIR):
            print(f"No data directory: {DATA_DIR}")
            sys.exit(0)

        files = sorted([f for f in os.listdir(DATA_DIR) if f.endswith(".json")])
        if not files:
            print("No price data files found.")
            sys.exit(0)

        print(f"{'File':<25} {'Status':<15} {'Age':>5} {'Tickers':>8} {'Last Date'}")
        print("-" * 75)
        for fname in files:
            fpath = os.path.join(DATA_DIR, fname)
            info = check_freshness(fpath)
            ticker_count = len(info['tickers'])
            # 取最近的 last_date
            last = max(info['last_dates'].values()) if info['last_dates'] else "N/A"
            print(f"{info['file']:<25} {info['status']:<15} {info['age_days']:>3}d  {ticker_count:>5}    {last}")

        # 提醒过期
        latest = os.path.join(DATA_DIR, files[-1])
        info = check_freshness(latest)
        if info['status'] == 'EXPIRED':
            print(f"\n⚠  Latest data is {info['age_days']} days old. Re-fetch recommended.")
        elif info['status'] == 'EXPIRING_SOON':
            print(f"\n⏰ Latest data expires in {EXPIRY_DAYS - info['age_days']} days.")
    else:
        print("Usage: python tools/save_prices.py --check")
        print("  Checks freshness of all price data files in data/prices/")


if __name__ == "__main__":
    main()
