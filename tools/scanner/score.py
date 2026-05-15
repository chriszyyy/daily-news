"""
L2 评分层 — 读 L1 JSON,硬约束过滤 + 4 维评分,产出排序 CSV。

用法:
  python tools/scanner/score.py \\
    --input data/scanner/raw-YYYY-MM-DD.json \\
    --output tools/scanner/output/YYYY-MM-DD-scan.csv \\
    [--chain pcb_hbm|cooling|power|optical|all]

评分公式见 .claude/plans/calm-doodling-teacup.md。
"""
import json
import sys
import io
import os
import csv
import argparse
from datetime import datetime, timezone, timedelta

if hasattr(sys.stdout, "buffer"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from ai_keywords import match_chain  # noqa: E402


# ─── 硬约束 ──────────────────────────────────────────────────────

HARD_FILTERS = {
    "price_max": 40.0,
    "market_cap_min": 30e8,
    "market_cap_max": 300e8,
    "year_change_max_pct": 150.0,           # 52w(用 ytd 代理)
    "year_change_max_pct_optical": 200.0,   # 光模块特例
    "exclude_st": True,
    "exclude_chinext": True,                # 300/301
    "exclude_bj": True,                     # 北交所(权限/流动性)
    "exclude_kechuang": True,               # 688 科创板(50w 权限门槛)
    "exclude_new_listing_days": 60,         # 上市 60 天内排除(避免次新爆炒)
}


def hard_filter(stock: dict, today: datetime) -> tuple[bool, str]:
    """返回 (是否通过, 不通过原因)"""
    code = stock.get("code", "")
    name = stock.get("name", "") or ""

    # ST
    if HARD_FILTERS["exclude_st"] and ("ST" in name or "*" in name):
        return False, "ST"

    # 创业板
    if HARD_FILTERS["exclude_chinext"] and (code.startswith("300") or code.startswith("301")):
        return False, "创业板"

    # 科创板
    if HARD_FILTERS["exclude_kechuang"] and code.startswith("688"):
        return False, "科创板"

    # 北交所
    if HARD_FILTERS["exclude_bj"] and (code.startswith("4") or code.startswith("8") or code.startswith("9")):
        return False, "北交所"

    # 价格
    price = stock.get("price")
    if price is None or price <= 0:
        return False, "无价"
    if price > HARD_FILTERS["price_max"]:
        return False, f"价格>¥{HARD_FILTERS['price_max']}"

    # 市值
    mc = stock.get("market_cap")
    if mc is None or mc <= 0:
        return False, "无市值"
    if mc < HARD_FILTERS["market_cap_min"]:
        return False, "市值<¥30亿"
    if mc > HARD_FILTERS["market_cap_max"]:
        return False, "市值>¥300亿"

    # 上市日期
    ld = stock.get("list_date")
    if ld and HARD_FILTERS["exclude_new_listing_days"] > 0:
        try:
            ld_dt = datetime.strptime(str(int(ld)), "%Y%m%d")
            age_days = (today - ld_dt).days
            if age_days < HARD_FILTERS["exclude_new_listing_days"]:
                return False, f"次新({age_days}d)"
        except Exception:
            pass

    return True, ""


# ─── 4 维评分 ────────────────────────────────────────────────────

def score_valuation(pe: float | None, pb: float | None) -> tuple[float, dict]:
    """估值 30 分:PE 越低越高(20),PB 越低越高(10)"""
    detail = {}
    pe_score = 0
    if pe is not None and pe > 0:
        if pe < 20:
            pe_score = 20
        elif pe < 30:
            pe_score = 15
        elif pe < 50:
            pe_score = 8
        else:
            pe_score = 0
    detail["pe_score"] = pe_score

    pb_score = 0
    if pb is not None and pb > 0:
        if pb < 3:
            pb_score = 10
        elif pb < 5:
            pb_score = 6
        elif pb < 8:
            pb_score = 3
        else:
            pb_score = 0
    detail["pb_score"] = pb_score

    return pe_score + pb_score, detail


def score_performance(stock: dict) -> tuple[float, dict]:
    """
    业绩 30 分。L2 缺 Q1 净利数据(L3 Yahoo 补),用代理:
      - 60d 涨幅适度正 (>+10% 加分,被市场认可)
      - 换手率适度 (1-5% 健康,>10% 过热扣)
      - turnover_yuan(成交额) 不直接打分,作为流动性参考
    粗筛代理,L3 用真实 Q1/forwardPE 精算。
    """
    detail = {}
    score = 0

    # 60d 涨幅 — 中性偏好
    chg60 = stock.get("change_60d_pct")
    chg60_score = 0
    if chg60 is not None:
        if 5 <= chg60 <= 50:
            chg60_score = 15  # 趋势确认且未疯涨
        elif 0 < chg60 < 5:
            chg60_score = 10  # 启动初期
        elif 50 < chg60 <= 100:
            chg60_score = 5   # 涨幅大,警惕回撤
        elif -10 <= chg60 < 0:
            chg60_score = 8   # 浅回调
        else:
            chg60_score = 0
    detail["chg60_score"] = chg60_score

    # 换手率
    tr = stock.get("turnover_rate_pct")
    tr_score = 0
    if tr is not None:
        if 1 <= tr <= 5:
            tr_score = 15
        elif 5 < tr <= 10:
            tr_score = 10
        elif 0.3 <= tr < 1:
            tr_score = 5
        else:
            tr_score = 0   # 过热(>10) 或 死水(<0.3)
    detail["turnover_rate_score"] = tr_score

    score = chg60_score + tr_score
    return score, detail


def score_technical(stock: dict) -> tuple[float, dict]:
    """
    技术 20 分。L2 无 30d 历史,用 spot 字段代理:
      - 距 ytd 高位距离(用 ytd 涨幅反推 — 涨幅小 = 离高位近 = 扣分;涨幅适中 = 仍有空间)
      - 价格在今日 high/low 区间位置(尾盘强 = 加分)
    """
    detail = {}
    ytd = stock.get("change_ytd_pct")
    ytd_score = 0
    if ytd is not None:
        # 完美区间:0-30% (有上涨但仍有空间)
        if -20 <= ytd <= 0:
            ytd_score = 12   # 浅亏,潜在反转
        elif 0 < ytd <= 30:
            ytd_score = 15   # 健康上涨
        elif 30 < ytd <= 80:
            ytd_score = 10   # 已涨较多
        elif -40 <= ytd < -20:
            ytd_score = 5    # 深调,需更多确认
        else:
            ytd_score = 0
    detail["ytd_score"] = ytd_score

    # 今日强度:close 在 (low, high) 中的位置
    p = stock.get("price")
    h = stock.get("high_today")
    l = stock.get("low_today")
    pos_score = 0
    if p and h and l and h > l:
        pos = (p - l) / (h - l)  # 0=最低, 1=最高
        if pos >= 0.7:
            pos_score = 5   # 收高,强势
        elif pos >= 0.4:
            pos_score = 3   # 中性
        else:
            pos_score = 1   # 弱势
    detail["intraday_strength_score"] = pos_score

    return ytd_score + pos_score, detail


def score_ai_relevance(stock: dict) -> tuple[float, dict, str | None]:
    """AI 关联度 20 分。返回 (score, detail, chain_id)"""
    name = stock.get("name", "")
    industry = stock.get("industry", "")
    chain, strength, sc = match_chain(name, industry)
    return sc, {"chain": chain, "match_strength": strength, "ai_score": sc}, chain


def score_one(stock: dict, today: datetime) -> dict:
    """单只全维度评分。返回扁平 dict(可写 CSV)"""
    passed, reason = hard_filter(stock, today)

    val_score, val_detail = score_valuation(stock.get("pe_ttm"), stock.get("pb"))
    perf_score, perf_detail = score_performance(stock)
    tech_score, tech_detail = score_technical(stock)
    ai_score, ai_detail, chain = score_ai_relevance(stock)

    total = val_score + perf_score + tech_score + ai_score

    mc = stock.get("market_cap")
    mc_yi = round(mc / 1e8, 1) if mc else None

    return {
        "code": stock.get("code"),
        "name": stock.get("name"),
        "exchange": stock.get("exchange"),
        "chain": chain or "",
        "match_strength": ai_detail["match_strength"],
        "score_total": round(total, 1),
        "score_valuation": val_score,
        "score_performance": perf_score,
        "score_technical": tech_score,
        "score_ai": ai_score,
        "price": stock.get("price"),
        "market_cap_yi": mc_yi,
        "pe_ttm": stock.get("pe_ttm"),
        "pb": stock.get("pb"),
        "change_pct": stock.get("change_pct"),
        "change_60d_pct": stock.get("change_60d_pct"),
        "change_ytd_pct": stock.get("change_ytd_pct"),
        "turnover_rate_pct": stock.get("turnover_rate_pct"),
        "industry": stock.get("industry"),
        "hard_filter_pass": passed,
        "hard_filter_reason": reason,
    }


# ─── 主流程 ──────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True, help="L1 JSON 路径")
    parser.add_argument("--output", default=None, help="CSV 输出路径")
    parser.add_argument("--chain", default="all",
                        choices=["all", "pcb_hbm", "cooling", "power", "optical"],
                        help="只输出指定链,默认 all")
    parser.add_argument("--top", type=int, default=200,
                        help="CSV 只保留 Top N(默认 200)")
    args = parser.parse_args()

    bjt = timezone(timedelta(hours=8))
    today = datetime.now(bjt).replace(tzinfo=None)

    if args.output is None:
        today_str = today.strftime("%Y-%m-%d")
        out_dir = os.path.join(os.path.dirname(__file__), "output")
        os.makedirs(out_dir, exist_ok=True)
        args.output = os.path.join(out_dir, f"{today_str}-scan.csv")

    print(f"[score] 读取 {args.input}", flush=True)
    with open(args.input, encoding="utf-8") as f:
        data = json.load(f)

    stocks = data.get("stocks", [])
    print(f"[score] 输入 {len(stocks)} 只", flush=True)

    # 评分
    scored = [score_one(s, today) for s in stocks]

    # 过滤 — 只保留通过硬约束的
    passed = [s for s in scored if s["hard_filter_pass"]]
    print(f"[score] 通过硬约束 {len(passed)} 只", flush=True)

    # 只保留 AI 链命中的
    ai_hits = [s for s in passed if s["chain"]]
    print(f"[score] AI 链命中 {len(ai_hits)} 只", flush=True)

    # 链筛选
    if args.chain != "all":
        ai_hits = [s for s in ai_hits if s["chain"] == args.chain]
        print(f"[score] 链筛选({args.chain}) {len(ai_hits)} 只", flush=True)

    # 排序 + Top N
    ai_hits.sort(key=lambda x: x["score_total"], reverse=True)
    top_n = ai_hits[: args.top]

    # 写 CSV
    if not top_n:
        print(f"[score] 警告:无候选,生成空 CSV", flush=True)

    fieldnames = [
        "score_total", "chain", "code", "name", "price", "market_cap_yi",
        "pe_ttm", "pb", "change_pct", "change_60d_pct", "change_ytd_pct",
        "turnover_rate_pct", "industry", "match_strength",
        "score_valuation", "score_performance", "score_technical", "score_ai",
        "exchange", "hard_filter_pass", "hard_filter_reason",
    ]
    with open(args.output, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        for row in top_n:
            w.writerow({k: row.get(k, "") for k in fieldnames})

    print(f"[done] Top {len(top_n)} → {args.output}", flush=True)

    # 控制台 Top 10 预览
    print("\n[Top 10 preview]")
    print(f"{'rank':<5}{'score':<7}{'chain':<10}{'code':<8}{'name':<14}{'price':<8}{'mc(亿)':<10}{'pe':<8}{'industry'}")
    for i, r in enumerate(top_n[:10], 1):
        print(f"{i:<5}{r['score_total']:<7}{(r['chain'] or ''):<10}{r['code']:<8}{r['name']:<14}{r['price']:<8}{r['market_cap_yi']:<10}{r['pe_ttm'] or 'N/A':<8}{r['industry']}")


if __name__ == "__main__":
    main()
