"""财联社电报实时监测: 抓取快讯 -> 过滤(重要标记 + 行业主题词) -> 去重 -> 推送。

数据源: https://www.cls.cn/v1/roll/get_roll_list (web 签名接口, 无需登录)
过滤: level in (A,B) 重要电报  OR  命中行业主题词 (content/subjects/plate_list 多字段)
去重: state/telegraph_seen.json 记录已推送 id, 只推新增
推送: 复用 notify (Server酱)

用法:
  python cls_telegraph.py --once          # 抓一次, 推送命中的新快讯
  python cls_telegraph.py --loop 600      # 每 600 秒循环 (盘中监测)
  python cls_telegraph.py --once --dry     # 只打印命中, 不推送 (调试)
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import time
from datetime import datetime
from urllib.parse import urlencode

import requests

BASE_DIR = os.path.dirname(os.path.dirname(__file__))
STATE_DIR = os.path.join(BASE_DIR, "state")
SEEN_PATH = os.path.join(STATE_DIR, "telegraph_seen.json")

CLS_URL = "https://www.cls.cn/v1/roll/get_roll_list"
HEADERS = {
    "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                   "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120 Safari/537.36"),
    "Referer": "https://www.cls.cn/telegraph",
}

# 重要电报等级 (财联社红色标记 = A/B)
IMPORTANT_LEVELS = {"A", "B"}

# 行业主题词: 复用 orchestrator.HOT_SECTOR_KEYWORDS + 快讯口语高频词
THEME_KEYWORDS = (
    # 与 orchestrator.HOT_SECTOR_KEYWORDS 对齐
    "半导体", "电子", "通信", "计算机", "光学", "元件",
    "电力", "电网", "自动化", "机器人", "通用设备", "专用设备",
    # 快讯高频主题词 (更细/更口语)
    "芯片", "算力", "AI", "人工智能", "大模型", "GPU", "英伟达", "华为",
    "人形机器人", "机器狗", "减速器", "丝杠",
    "固态电池", "锂电", "储能", "光伏", "钙钛矿",
    "光模块", "CPO", "PCB", "先进封装", "HBM", "存储", "液冷", "数据中心", "智算",
    "自动驾驶", "低空经济", "eVTOL", "无人机",
    "创新药", "减肥药", "GLP",
    "稀土", "小金属", "新材料", "军工", "国产替代",
)

# 主题匹配时扫描的字段 (多字段命中提高精度)
MATCH_FIELDS = ("content", "title", "brief", "share_content")


def _sign(params: dict) -> dict:
    """财联社 web 签名: 参数按 key 排序 -> querystring -> sha1 -> md5。"""
    qs = urlencode(sorted(params.items()))
    sha1 = hashlib.sha1(qs.encode()).hexdigest()
    sign = hashlib.md5(sha1.encode()).hexdigest()
    return {**params, "sign": sign}


def fetch_telegraph(rn: int = 30) -> list[dict]:
    """抓取最新 rn 条电报。失败返回空列表 (不抛异常, 保证调度不中断)。"""
    params = {
        "app": "CailianpressWeb", "os": "web", "sv": "7.7.5",
        "category": "", "last_time": "", "refresh_type": "1", "rn": str(rn),
    }
    url = CLS_URL + "?" + urlencode(_sign(params))
    try:
        r = requests.get(url, headers=HEADERS, timeout=15)
        d = r.json()
        if str(d.get("errno")) != "0":
            print(f"[cls] 接口错误: errno={d.get('errno')} msg={d.get('msg')}")
            return []
        return d.get("data", {}).get("roll_data", []) or []
    except Exception as e:  # noqa: BLE001
        print(f"[cls] 抓取失败: {e}")
        return []


def _matched_themes(item: dict) -> list[str]:
    """返回该电报命中的主题词列表 (扫多字段 + 结构化 subjects/plate_list/stock_list)。"""
    text = " ".join(str(item.get(f) or "") for f in MATCH_FIELDS)
    # 结构化字段: 板块/主题/个股名一起并入文本
    for key in ("subjects", "plate_list", "stock_list", "tags"):
        for x in (item.get(key) or []):
            if isinstance(x, dict):
                text += " " + str(x.get("name") or x.get("subject") or "")
            else:
                text += " " + str(x)
    hits = [kw for kw in THEME_KEYWORDS if kw in text]
    # 去重保序
    seen = set()
    return [h for h in hits if not (h in seen or seen.add(h))]


def classify(item: dict) -> dict | None:
    """判断电报是否该推送。返回 {原因, 主题, ...} 或 None (不推)。"""
    level = str(item.get("level") or "C")
    is_important = level in IMPORTANT_LEVELS
    themes = _matched_themes(item)
    if not is_important and not themes:
        return None
    reasons = []
    if is_important:
        reasons.append(f"重要({level})")
    if themes:
        reasons.append("主题:" + "/".join(themes[:5]))
    return {
        "id": item.get("id"),
        "ctime": item.get("ctime"),
        "level": level,
        "important": is_important,
        "themes": themes,
        "reason": " ".join(reasons),
        "content": (item.get("content") or item.get("brief") or "").strip(),
        "stocks": [s.get("name") for s in (item.get("stock_list") or []) if isinstance(s, dict)],
        "reading": item.get("reading_num"),
    }


def _load_seen() -> set:
    try:
        with open(SEEN_PATH, encoding="utf-8") as f:
            return set(json.load(f))
    except Exception:  # noqa: BLE001
        return set()


def _save_seen(seen: set, cap: int = 2000) -> None:
    os.makedirs(STATE_DIR, exist_ok=True)
    # 只保留最近 cap 个 id, 防文件无限增长
    keep = list(seen)[-cap:]
    with open(SEEN_PATH, "w", encoding="utf-8") as f:
        json.dump(keep, f, ensure_ascii=False)


def _fmt_push(hits: list[dict]) -> tuple[str, str]:
    """把命中电报组装成推送标题+正文。"""
    n = len(hits)
    n_imp = sum(1 for h in hits if h["important"])
    title = f"📡 财联社快讯 {n}条 (重要{n_imp}) {datetime.now():%H:%M}"
    lines = []
    for h in hits:
        t = datetime.fromtimestamp(h["ctime"]).strftime("%H:%M") if h.get("ctime") else ""
        flag = "🔴" if h["important"] else "🟡"
        lines.append(f"{flag} **{t}** [{h['reason']}]")
        lines.append(h["content"][:220])
        if h["stocks"]:
            lines.append("关联: " + " ".join(h["stocks"][:6]))
        lines.append("")
    return title, "\n".join(lines).strip()


def run_once(dry: bool = False, rn: int = 30) -> int:
    """抓一次, 过滤+去重, 推送命中的新快讯。返回推送条数。"""
    items = fetch_telegraph(rn=rn)
    if not items:
        return 0
    seen = _load_seen()
    hits = []
    new_ids = []
    for it in items:
        cid = it.get("id")
        if cid in seen:
            continue
        c = classify(it)
        if c:
            hits.append(c)
        new_ids.append(cid)   # 待标记 (仅真实推送后才写入, dry 不污染)

    if not hits:
        if not dry:
            seen.update(new_ids)
            _save_seen(seen)
        print(f"[cls] 抓 {len(items)} 条, 无新命中")
        return 0
    # 按时间正序 (老->新) 更符合阅读
    hits.sort(key=lambda h: h.get("ctime") or 0)
    title, body = _fmt_push(hits)
    print(f"[cls] 命中 {len(hits)} 条:")
    for h in hits:
        print(f"  {h['reason']} | {h['content'][:60]}")

    if dry:
        print("\n--- DRY RUN, 不推送 (不写 seen) ---\n" + title + "\n\n" + body[:500])
        return len(hits)

    import sys
    sys.path.insert(0, os.path.dirname(__file__))
    import notify
    cfg = notify._load_config()
    key = cfg.get("serverchan_key")
    if key and notify._push_serverchan(key, title, body):
        print(f"[cls] 已推送 Server酱: {len(hits)} 条")
    else:
        notify._local_log(title, body)
        print("[cls] Server酱 未配置/失败, 已存本地日志")
    seen.update(new_ids)   # 推送后才标记已读
    _save_seen(seen)
    return len(hits)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--once", action="store_true", help="抓一次")
    ap.add_argument("--loop", type=int, default=0, help="循环间隔秒 (0=不循环)")
    ap.add_argument("--dry", action="store_true", help="只打印不推送")
    ap.add_argument("--rn", type=int, default=30, help="每次抓取条数")
    args = ap.parse_args()

    if args.loop:
        print(f"[cls] 循环监测, 间隔 {args.loop}s (Ctrl+C 停止)")
        while True:
            try:
                run_once(dry=args.dry, rn=args.rn)
            except Exception as e:  # noqa: BLE001
                print(f"[cls] 本轮异常 (继续): {e}")
            time.sleep(args.loop)
    else:
        run_once(dry=args.dry, rn=args.rn)


if __name__ == "__main__":
    main()
