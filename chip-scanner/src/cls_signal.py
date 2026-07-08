"""财联社次日强动量候选 — 每日生成 + 前向验证 + 留档。

工作闭环 (每交易日收盘后跑一次):
  1. verify: 回填历史候选的实际次日收益 → 追加 validation.csv → 算滚动胜率 → 推送验证小结。
  2. generate: 从今日财联社快讯抽取"强动量候选" (关联 A 股盘中涨幅 RiseRange >= 阈值)
     → 存档 predictions/YYYYMMDD.json → 推送今日候选。

为什么这么做:
  历史回测 (cls_nextday_backtest.py) 显示: 财联社快讯提及"已大涨/涨停"的强势股,
  次日继续上涨的胜率显著高于全样本 (涨停桶 30d 胜率 64% / 次日均 +3.27%,
  基准沪深300 仅 +0.04%)。本模块把该"强动量子集"做成**每日实盘前向验证**,
  用真实次日结果持续检验回测结论是否可复现, 全部留档。

候选定义 (可调 --rise-min, 默认 6.0%):
  某只 A 股在当日任一条财联社快讯中 RiseRange >= rise-min。
  按 code 去重, 取当日最高 RiseRange 及其快讯作为代表。
  分档: S=涨停(≥9.5%) / A=6-9.5% / B=rise-min~6%。

数据/存档:
  data/cls_signals/predictions/YYYYMMDD.json   每日候选快照
  data/cls_signals/validation.csv              累计验证明细 (一候选一行)
  验证 = 次日 close(T+1)/close(T)-1; win = > +1.0% (与回测一致)。

用法:
  python src/cls_signal.py --daily            # 收盘后: 先 verify 再 generate (定时任务用)
  python src/cls_signal.py --generate         # 只生成今日候选
  python src/cls_signal.py --verify           # 只回填验证
  python src/cls_signal.py --daily --dry      # 不推送不写档 (调试)
  python src/cls_signal.py --rise-min 9.5     # 只要涨停级候选
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import sys
from datetime import date, datetime

_SRC_DIR = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_SRC_DIR)
DATA_DIR = os.path.join(_ROOT, "data", "cls_signals")
PRED_DIR = os.path.join(DATA_DIR, "predictions")
VALID_CSV = os.path.join(DATA_DIR, "validation.csv")
sys.path.insert(0, _SRC_DIR)

import cls_nextday_backtest as BT   # noqa: E402  抓取/kline/收益
import cls_telegraph as CLS         # noqa: E402  主题词/等级
import news_nextday_backtest as NB  # noqa: E402  next_day_return/情绪/胜率阈值

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:  # noqa: BLE001
        pass

RISE_MIN_DEFAULT = 6.0
VALID_FIELDS = ["trigger_day", "code", "name", "rise", "tier", "board", "tradable",
                "reason", "close_t", "t1_date", "close_t1", "ret_pct", "win",
                "verified_at"]


def log(msg: str) -> None:
    print(f"{datetime.now():%H:%M:%S} {msg}", flush=True)


def _tier(rise: float) -> str:
    if rise >= 9.5:
        return "S涨停"
    if rise >= 6.0:
        return "A强势"
    return "B活跃"


def _board(code: str) -> str:
    if code.startswith(("300", "301")):
        return "创业板"
    if code.startswith("688"):
        return "科创板"
    if code.startswith(("83", "87", "43", "92")):
        return "北交所"
    return "主板"


def _tradable(code: str) -> bool:
    """当前账户可交易性: 创业板 300/301 无权限; 科创板 688 需单独权限 (谨慎标注)。"""
    return _board(code) in ("主板", "北交所")


def _is_trading_day(d: date) -> bool:
    return d.weekday() < 5   # 简易: 周一~五 (节假日暂不排除)


# ----------------------------- 生成今日候选 -----------------------------

def generate(rise_min: float, dry: bool) -> list[dict]:
    """从今日财联社快讯抽强动量候选, 存档 + 推送。返回候选列表。"""
    today = date.today()
    if not _is_trading_day(today):
        log("非交易日, 不生成候选")
        return []
    ds = today.isoformat()
    log(f"生成今日候选 | {ds} | RiseRange >= {rise_min}%")
    items = BT.fetch_telegraph_history(ds, ds, throttle=0.3, max_pages=60)
    if not items:
        log("今日无快讯")
        return []

    # code -> 最佳候选 (取当日最高 RiseRange)
    best: dict[str, dict] = {}
    for it in items:
        stocks = BT._a_share_stocks(it)
        if not stocks:
            continue
        content = (it.get("content") or it.get("brief") or "").strip()
        themes = CLS._matched_themes(it)
        senti = NB.sentiment("", content)
        level = str(it.get("level") or "C")
        for st in stocks:
            rise = st.get("rise")
            try:
                rise = float(rise)
            except (TypeError, ValueError):
                continue
            if rise < rise_min:
                continue
            code = st["code"]
            prev = best.get(code)
            if prev and prev["rise"] >= rise:
                continue
            reasons = []
            if level in CLS.IMPORTANT_LEVELS:
                reasons.append(f"重要{level}")
            if themes:
                reasons.append("主题:" + "/".join(themes[:3]))
            if senti == "pos":
                reasons.append("利好")
            best[code] = {
                "code": code, "name": st.get("name") or "",
                "rise": round(rise, 2), "tier": _tier(rise),
                "board": _board(code), "tradable": _tradable(code),
                "themes": "/".join(themes[:4]),
                "sentiment": senti, "level": level,
                "reason": " ".join(reasons) or "盘中强势",
                "content": content[:100],
            }

    cands = sorted(best.values(), key=lambda c: -c["rise"])
    log(f"命中候选 {len(cands)} 只")
    if not cands:
        return []

    # 记录触发日收盘价 (T = 今日), 供次日验证基准
    for c in cands:
        dated = BT.NB.fetch_kline_dated(c["code"])
        c["close_t"] = None
        if dated:
            for d in dated:
                if d["date"] == ds:
                    c["close_t"] = d["close"]
                    break

    if not dry:
        os.makedirs(PRED_DIR, exist_ok=True)
        path = os.path.join(PRED_DIR, f"{today:%Y%m%d}.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump({"trigger_day": ds, "rise_min": rise_min,
                       "generated_at": datetime.now().isoformat(timespec="seconds"),
                       "candidates": cands}, f, ensure_ascii=False, indent=2)
        log(f"存档 → {path}")

    _push_candidates(ds, cands, dry)
    return cands


def _push_candidates(ds: str, cands: list[dict], dry: bool) -> None:
    n_s = sum(1 for c in cands if c["tier"].startswith("S"))
    n_tradable = sum(1 for c in cands if c.get("tradable"))
    title = f"🎯 财联社次日候选 {len(cands)}只 (可交易{n_tradable}/涨停{n_s}) {ds[5:]}"
    # 可交易的排前面, 创业板/科创板降序其后
    ordered = sorted(cands, key=lambda c: (not c.get("tradable"), -c["rise"]))
    lines = ["**次日强动量候选** (快讯提及+盘中强势, 观察T+1)\n"]
    for c in ordered[:24]:
        flag = "🔴" if c["tier"].startswith("S") else ("🟠" if c["tier"].startswith("A") else "🟡")
        perm = "" if c.get("tradable") else f" ⚠️{c.get('board', '')}无权限"
        lines.append(f"{flag} {c['name']}({c['code']}) +{c['rise']}% [{c['tier']}]{perm}")
        if c["reason"]:
            lines.append(f"   {c['reason']}")
    if len(cands) > 24:
        lines.append(f"... 另 {len(cands) - 24} 只见存档")
    lines.append("\n⚠️ 前向验证研究, 非投资建议; 追涨停有一字板买不进风险")
    body = "\n".join(lines)
    _push(title, body, dry, tag="候选")


# ----------------------------- 验证历史候选 -----------------------------

def _load_verified_keys() -> set:
    """已验证的 (trigger_day, code) 集合, 避免重复写入。"""
    keys = set()
    if os.path.exists(VALID_CSV):
        with open(VALID_CSV, encoding="utf-8-sig") as f:
            for row in csv.DictReader(f):
                keys.add((row["trigger_day"], row["code"]))
    return keys


def verify(dry: bool) -> list[dict]:
    """回填所有"已到期但未验证"的历史候选实际次日收益。"""
    if not os.path.isdir(PRED_DIR):
        log("无历史候选存档, 跳过验证")
        return []
    verified = _load_verified_keys()
    new_rows: list[dict] = []
    pred_files = sorted(f for f in os.listdir(PRED_DIR) if f.endswith(".json"))
    for fn in pred_files:
        with open(os.path.join(PRED_DIR, fn), encoding="utf-8") as f:
            pred = json.load(f)
        T = pred["trigger_day"]
        for c in pred.get("candidates", []):
            key = (T, c["code"])
            if key in verified:
                continue
            dated = BT.NB.fetch_kline_dated(c["code"])
            if not dated:
                continue
            nd = NB.next_day_return(dated, T)
            if nd["ret_pct"] is None:      # T+1 尚未产生, 留待下次
                continue
            new_rows.append({
                "trigger_day": T, "code": c["code"], "name": c.get("name", ""),
                "rise": c.get("rise"), "tier": c.get("tier", ""),
                "board": c.get("board") or _board(c["code"]),
                "tradable": int(c.get("tradable", _tradable(c["code"]))),
                "reason": c.get("reason", ""),
                "close_t": c.get("close_t") or nd["trigger_close"],
                "t1_date": nd["t1_date"], "close_t1": nd["t1_close"],
                "ret_pct": nd["ret_pct"],
                "win": int(nd["ret_pct"] > NB.WIN_THRESHOLD_PCT),
                "verified_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
            })
    if new_rows:
        log(f"本次新验证 {len(new_rows)} 条候选")
        if not dry:
            _append_validation(new_rows)
    else:
        log("无到期候选可验证")

    _push_verification(new_rows, dry)
    return new_rows


def _append_validation(rows: list[dict]) -> None:
    os.makedirs(DATA_DIR, exist_ok=True)
    exists = os.path.exists(VALID_CSV)
    with open(VALID_CSV, "a", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=VALID_FIELDS)
        if not exists:
            w.writeheader()
        for r in rows:
            w.writerow({k: r.get(k, "") for k in VALID_FIELDS})
    log(f"追加 → {VALID_CSV}")


def _running_stats() -> dict:
    """累计验证胜率 (全部 + 按档)。"""
    if not os.path.exists(VALID_CSV):
        return {}
    rows = []
    with open(VALID_CSV, encoding="utf-8-sig") as f:
        for r in csv.DictReader(f):
            try:
                r["ret_pct"] = float(r["ret_pct"])
                r["win"] = int(r["win"])
            except (ValueError, KeyError):
                continue
            rows.append(r)
    if not rows:
        return {}

    def agg(sub):
        n = len(sub)
        if not n:
            return None
        wins = sum(x["win"] for x in sub)
        avg = sum(x["ret_pct"] for x in sub) / n
        up = sum(1 for x in sub if x["ret_pct"] > 0)
        return {"n": n, "win_rate": wins / n, "avg": avg, "up_rate": up / n}

    out = {"ALL": agg(rows)}
    tradable = [r for r in rows if str(r.get("tradable", "")) in ("1", "True", "true")]
    if tradable:
        out["可交易"] = agg(tradable)
    for tier_key, label in (("S", "S涨停"), ("A", "A强势"), ("B", "B活跃")):
        sub = [r for r in rows if r.get("tier", "").startswith(tier_key)]
        if sub:
            out[label] = agg(sub)
    return out


def _push_verification(new_rows: list[dict], dry: bool) -> None:
    stats = _running_stats()
    if not stats and not new_rows:
        return
    all_s = stats.get("ALL")
    title = "✅ 财联社候选验证回填"
    if new_rows:
        hit = sum(r["win"] for r in new_rows)
        title = f"✅ 昨日候选验证 {hit}/{len(new_rows)}命中"
    lines = []
    if new_rows:
        lines.append(f"**本次验证 {len(new_rows)} 只** (次日>+1%算命中)\n")
        for r in sorted(new_rows, key=lambda x: -x["ret_pct"])[:15]:
            mark = "✅" if r["win"] else "❌"
            lines.append(f"{mark} {r['name']}({r['code']}) 次日{r['ret_pct']:+.2f}% [{r['tier']}]")
        lines.append("")
    if all_s:
        lines.append("**累计前向验证战绩**")
        lines.append(f"全样本: n={all_s['n']} 胜率{all_s['win_rate']:.0%} "
                     f"次日均{all_s['avg']:+.2f}% 上涨率{all_s['up_rate']:.0%}")
        tr = stats.get("可交易")
        if tr:
            lines.append(f"可交易(排除创业板): n={tr['n']} 胜率{tr['win_rate']:.0%} "
                         f"次日均{tr['avg']:+.2f}%")
        for label in ("S涨停", "A强势", "B活跃"):
            s = stats.get(label)
            if s:
                lines.append(f"{label}: n={s['n']} 胜率{s['win_rate']:.0%} "
                             f"次日均{s['avg']:+.2f}%")
    body = "\n".join(lines)
    _push(title, body, dry, tag="验证")


# ----------------------------- 推送 -----------------------------

def _push(title: str, body: str, dry: bool, tag: str = "") -> None:
    if dry:
        print(f"\n--- DRY [{tag}] 不推送 ---\n{title}\n{body}\n")
        return
    import notify
    cfg = notify._load_config()
    key = cfg.get("serverchan_key")
    if key and notify._push_serverchan(key, title, body):
        log(f"已推送 [{tag}]: {title}")
    else:
        notify._local_log(title, body)
        log(f"[{tag}] Server酱 未配置/失败, 已存本地日志")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--daily", action="store_true", help="收盘后: 先验证昨日再生成今日")
    ap.add_argument("--generate", action="store_true", help="只生成今日候选")
    ap.add_argument("--verify", action="store_true", help="只回填验证")
    ap.add_argument("--rise-min", type=float, default=RISE_MIN_DEFAULT,
                    help=f"候选盘中涨幅阈值%% (默认 {RISE_MIN_DEFAULT})")
    ap.add_argument("--dry", action="store_true", help="不推送不写档 (调试)")
    args = ap.parse_args()

    do_verify = args.daily or args.verify
    do_gen = args.daily or args.generate
    if not (do_verify or do_gen):
        do_verify = do_gen = True   # 默认等同 --daily

    if do_verify:
        verify(args.dry)
    if do_gen:
        generate(args.rise_min, args.dry)


if __name__ == "__main__":
    main()
