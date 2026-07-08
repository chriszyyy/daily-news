"""通知器 — 把每日筛选结果推送到手机, 多渠道 + 本地日志兜底。

支持渠道 (按 config.json 配置, 任一可用即推):
  - PushDeer  : https://api2.pushdeer.com/message/push?pushkey=KEY&text=...
  - Server酱³ : https://sctapi.ftqq.com/KEY.send
  - 企业微信机器人: webhook url (markdown + 图片需 base64)
  - 本地日志  : 始终写 output/alerts/alert_YYYYMMDD.md (兜底)

配置文件 (chip-scanner/config.json, 不存在则仅本地日志):
  {
    "pushdeer_key": "...",
    "serverchan_key": "...",
    "wecom_webhook": "https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=..."
  }
"""

from __future__ import annotations

import base64
import hashlib
import json
import os
import re
from datetime import datetime

import requests

ROOT = os.path.dirname(os.path.dirname(__file__))
CONFIG_PATH = os.path.join(ROOT, "config.json")
ALERT_DIR = os.path.join(ROOT, "output", "alerts")


def _load_config() -> dict:
    if os.path.exists(CONFIG_PATH):
        try:
            with open(CONFIG_PATH, encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError):
            pass
    return {}


def _build_text(recs: list[dict], passed: list[dict],
                trend_recs: list[dict] | None = None,
                hot_sectors: list[str] | None = None,
                push_recs: list[dict] | None = None) -> tuple[str, str]:
    """返回 (标题, markdown 正文)。"""
    ts = datetime.now().strftime("%Y-%m-%d %H:%M")
    title = f"筹码扫描 {datetime.now():%m-%d}: 单峰密集 Top{len(passed)}"

    def _num(v, fmt="{:.1f}", suffix=""):
        return (fmt.format(v) + suffix) if isinstance(v, (int, float)) else "—"

    lines = [
        f"## 筹码扫描结果 {ts}",
        "",
        "**策略池**",
        f"- 单峰密集: {len(passed)} 只",
        f"- 强趋势启动: {len(trend_recs or [])} 只",
        f"- 推盘观察: {len(push_recs or [])} 只",
        "",
    ]
    if hot_sectors:
        def _fmt_delta(v, suffix=""):
            if isinstance(v, (int, float)):
                return f"{v:+.2f}{suffix}"
            return "—"

        lines += [
            "### 今日热门板块",
            "",
        ]
        for item in hot_sectors[:8]:
            if isinstance(item, dict):
                name = item.get("industry", "")
                rank_delta = item.get("排名变化")
                rank_txt = f"{rank_delta:+.0f}" if isinstance(rank_delta, (int, float)) else "新/—"
                amt = _num(item.get("成交额亿"), "{:.0f}", "亿")
                amt_delta = _fmt_delta(item.get("成交额变化亿"), "亿")
                median = _num(item.get("中位涨幅"), "{:+.2f}", "%")
                up = _num((item.get("上涨占比") or 0) * 100, "{:.0f}", "%") \
                    if isinstance(item.get("上涨占比"), (int, float)) else "—"
                score = _num(item.get("热度分"), "{:.1f}")
                score_delta = _fmt_delta(item.get("热度变化"))
                lines.append(
                    f"- **{name}**: 热度 {score}({score_delta}) / 排名Δ {rank_txt} / "
                    f"中位涨 {median} / 上涨 {up} / 成交 {amt}({amt_delta})"
                )
            else:
                lines.append(f"- {item}")
        lines.append("")
        if any(isinstance(item, dict) for item in hot_sectors):
            movers = [item for item in hot_sectors if isinstance(item, dict)]
            rank_up = [
                item for item in movers
                if isinstance(item.get("排名变化"), (int, float)) and item["排名变化"] > 0
            ]
            vol_up = [
                item for item in movers
                if isinstance(item.get("成交额变化亿"), (int, float)) and item["成交额变化亿"] > 20
            ]
            vol_down = [
                item for item in movers
                if isinstance(item.get("成交额变化亿"), (int, float)) and item["成交额变化亿"] < -20
            ]
            if rank_up or vol_up or vol_down:
                lines += ["**板块变化提示**"]
                if rank_up:
                    msg = " / ".join(
                        f"{x['industry']} 排名+{x['排名变化']:.0f}" for x in rank_up[:3]
                    )
                    lines.append(f"- 排名上升: {msg}")
                if vol_up:
                    msg = " / ".join(
                        f"{x['industry']} 成交+{x['成交额变化亿']:.0f}亿" for x in vol_up[:3]
                    )
                    lines.append(f"- 放量流入: {msg}")
                if vol_down:
                    msg = " / ".join(
                        f"{x['industry']} 成交{x['成交额变化亿']:.0f}亿" for x in vol_down[:3]
                    )
                    lines.append(f"- 缩量降温: {msg}")
                lines.append("")
    def add_high_section(title_text: str, items: list[dict], max_items: int = 10):
        if not items:
            return
        lines.extend(["", f"### {title_text}", ""])
        lines.append("> 格式: 形态 / 资金 / 业绩 / 量价")
        lines.append("")
        for i, r in enumerate(items[:max_items], 1):
            def _f(v, suf="%"):
                return f"{v:+.0f}{suf}" if isinstance(v, (int, float)) else "—"
            np_yoy = _f(r.get("净利润同比"))
            rev_yoy = _f(r.get("营收同比"))
            roe = _num(r.get("ROE"), "{:.1f}", "%")
            vr = _num(r.get("量比"), "{:.1f}")
            amt = _num(r.get("成交额亿"), "{:.1f}", "亿")
            main = (f"{r['主力净流入亿']:+.2f}亿/{r.get('主力净占比'):+.1f}%"
                    if isinstance(r.get("主力净流入亿"), (int, float))
                    and isinstance(r.get("主力净占比"), (int, float)) else "—")
            super_flow = (f"{r['超大单净流入亿']:+.2f}亿"
                          if isinstance(r.get("超大单净流入亿"), (int, float))
                          else "—")
            large = (f"{r['大单净流入亿']:+.2f}亿"
                     if isinstance(r.get("大单净流入亿"), (int, float)) else "—")
            fund_mark = "✓" if r.get("资金确认") == "是" else "—"
            pe = _num(r.get("PE"), "{:.0f}")
            price = _num(r.get("price"), "{:.2f}")
            lines.extend([
                f"- **{i}. {r['code']} {r['name']}** ({r.get('industry','')})",
                f"  - 类型: {r.get('单峰类型', '普通单峰')}",
                f"  - 价格/估值: {price} / PE {pe}",
                f"  - 形态: 带宽 {r['带宽70']:.0%} / 次峰 {r['次峰比']:.2f} / 距峰 {r['距主峰']:+.0%}",
                f"  - 资金{fund_mark}: 主力 {main} / 超大 {super_flow} / 大单 {large}",
                f"  - 业绩: 净利 {np_yoy} / 营收 {rev_yoy} / ROE {roe}",
                f"  - 量价: 量比 {vr} / 额 {amt}",
                "",
            ])
        if len(items) > max_items:
            lines.append(f"_另有 {len(items) - max_items} 只, 见 high_pool CSV_")

    trend_recs = trend_recs or []
    b_trends = [r for r in trend_recs if r.get("趋势档位") == "B-趋势确认"]
    a_trends = [r for r in trend_recs if r.get("趋势档位") == "A-主线新高"]
    c_trends = [r for r in trend_recs if str(r.get("趋势档位", "")).startswith("C-")]

    if b_trends:
        lines += ["", "### B档趋势确认（主观察池）", ""]
        for i, r in enumerate(b_trends[:10], 1):
            breakout = "新高" if r.get("突破20日新高") else "近高"
            ma = "多头" if r.get("均线多头") else "站上MA20"
            pe = f"{r.get('PE'):.0f}" if isinstance(r.get("PE"), (int, float)) else "—"
            lines += [
                f"- **B{i}. {r['code']} {r['name']}** ({r.get('industry','')})",
                f"  - 趋势: 5日 {r['近5日涨幅']:+.1f}% / 20日 {r['近20日涨幅']:+.1f}% / {breakout} {r['接近20日高点']:.0%} / {ma}",
                f"  - 量价: 放量比 {r.get('放量比')} / 额 {r.get('成交额亿')}亿 / PE {pe} / 分 {r.get('趋势分')}",
                "",
            ]

    if a_trends:
        lines += ["", "### A档主线新高（不过热才看）", ""]
        for i, r in enumerate(a_trends[:8], 1):
            pe = f"{r.get('PE'):.0f}" if isinstance(r.get("PE"), (int, float)) else "—"
            lines += [
                f"- **A{i}. {r['code']} {r['name']}** ({r.get('industry','')})",
                f"  - 趋势: 5日 {r['近5日涨幅']:+.1f}% / 20日 {r['近20日涨幅']:+.1f}% / 新高 {r['接近20日高点']:.0%}",
                f"  - 量价: 放量比 {r.get('放量比')} / 额 {r.get('成交额亿')}亿 / PE {pe} / 分 {r.get('趋势分')}",
                "",
            ]

    if c_trends:
        lines += ["", "### C档观察/过热（不追）", ""]
        for i, r in enumerate(c_trends[:6], 1):
            lines.append(
                f"- **C{i}. {r['code']} {r['name']}**: {r.get('趋势档位')} / "
                f"5日 {r['近5日涨幅']:+.1f}% / 20日 {r['近20日涨幅']:+.1f}% / "
                f"额 {r.get('成交额亿')}亿"
            )

    if not passed:
        lines.append("今日**无**符合条件的单峰密集标的。")
    else:
        offensive = [r for r in passed if r.get("单峰类型") == "进攻单峰"]
        defensive = [r for r in passed if r.get("单峰类型") == "防守单峰"]
        other = [r for r in passed if r.get("单峰类型") not in ("进攻单峰", "防守单峰")]
        add_high_section("进攻单峰（低位蓄势）", offensive, max_items=8)
        add_high_section("防守单峰（低波动/防守）", defensive, max_items=6)
        add_high_section("其他单峰", other, max_items=4)

    push_recs = push_recs or []
    if push_recs:
        lines += ["", "### 推盘观察池", ""]
        lines.append("> 仅提示资金推价痕迹，不作为买入建议；高位/过热默认只观察。")
        lines.append("")
        for i, r in enumerate(push_recs, 1):
            lines += [
                f"- **P{i}. {r['code']} {r['name']}** ({r.get('industry','')})",
                f"  - 观察: {r.get('推盘档位')} / 风险 {r.get('风险分层')}",
                f"  - 资金: 主力 {r['主力净流入亿']:+.2f}亿/{r['主力净占比']:+.1f}% / 超大 {r['超大单净流入亿']:+.2f}亿 / 大单 {r['大单净流入亿']:+.2f}亿",
                f"  - 强度: 收盘 {r['收盘强度']:.0%} / 5日 {r['近5日涨幅']:+.1f}% / 20日 {r['近20日涨幅']:+.1f}% / 分 {r.get('推盘分')}",
                "",
            ]

    lines += ["", f"_完整见 high_pool / trend_pool / push_pool CSV_"]
    body = "\n".join(lines)
    # Server酱/微信 Markdown 对连续块较敏感; 统一加空行提升可读性。
    body = body.replace("\n- **", "\n\n- **")
    body = body.replace("\n### ", "\n\n### ")
    body = body.replace("\n> ", "\n\n> ")
    return title, body


def _local_log(title: str, body: str) -> str:
    os.makedirs(ALERT_DIR, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d")
    path = os.path.join(ALERT_DIR, f"alert_{ts}.md")
    with open(path, "a", encoding="utf-8") as f:
        f.write(f"\n\n# {title}\n\n{body}\n")
    return path


def _push_pushdeer(key: str, title: str, body: str) -> bool:
    try:
        r = requests.post("https://api2.pushdeer.com/message/push",
                          data={"pushkey": key, "text": title,
                                "desp": body, "type": "markdown"}, timeout=10)
        return r.ok and r.json().get("code") == 0
    except Exception:  # noqa: BLE001
        return False


def _push_serverchan(key: str, title: str, body: str) -> bool:
    try:
        body = body.replace("\n", "\n\n")
        # Server酱³ (key 以 sctp 开头) 走独立域名 {uid}.push.ft07.com/send/{key}.send
        # 旧版 SC-T (sct 开头) 走 sctapi.ftqq.com/{key}.send
        m = re.match(r"sctp(\d+)t", key)
        if m:
            uid = m.group(1)
            url = f"https://{uid}.push.ft07.com/send/{key}.send"
        else:
            url = f"https://sctapi.ftqq.com/{key}.send"
        r = requests.post(url, data={"title": title, "desp": body}, timeout=10)
        return r.ok and r.json().get("code") == 0
    except Exception:  # noqa: BLE001
        return False


def _push_wecom(webhook: str, body: str) -> bool:
    try:
        r = requests.post(webhook, json={
            "msgtype": "markdown", "markdown": {"content": body}}, timeout=10)
        return r.ok and r.json().get("errcode") == 0
    except Exception:  # noqa: BLE001
        return False


def _push_wecom_image(webhook: str, img_path: str) -> bool:
    try:
        with open(img_path, "rb") as f:
            data = f.read()
        b64 = base64.b64encode(data).decode()
        md5 = hashlib.md5(data).hexdigest()
        r = requests.post(webhook, json={
            "msgtype": "image",
            "image": {"base64": b64, "md5": md5}}, timeout=15)
        return r.ok and r.json().get("errcode") == 0
    except Exception:  # noqa: BLE001
        return False


def send_daily(recs: list[dict], passed: list[dict],
               charts: dict[str, str] | None = None,
               overview_path: str | None = None,
               trend_recs: list[dict] | None = None,
               hot_sectors: list[str] | None = None,
               push_recs: list[dict] | None = None,
               sector_chart_path: str | None = None) -> None:
    """发送每日通知。recs=全部High, passed=入选, overview_path=总览图本地路径,
    sector_chart_path=板块热度图本地路径。"""
    cfg = _load_config()
    title, body = _build_text(recs, passed, trend_recs=trend_recs,
                              hot_sectors=hot_sectors, push_recs=push_recs)

    # 图: push 到公开仓库, 取 jsDelivr CDN URL, 嵌入 Markdown
    try:
        import git_image
    except Exception:  # noqa: BLE001
        git_image = None

    # 板块热度图放正文最前 (最直观), 总览图次之
    sector_url = None
    if sector_chart_path and git_image:
        try:
            sector_url = git_image.upload_image(sector_chart_path, name="sector")
        except Exception as e:  # noqa: BLE001
            print(f"[notify] 板块图上传失败: {e}")
    img_url = None
    if overview_path and git_image:
        try:
            img_url = git_image.upload_image(overview_path, name="latest")
        except Exception as e:  # noqa: BLE001
            print(f"[notify] 图床上传失败: {e}")
    if img_url:
        body = f"![单峰密集总览]({img_url})\n\n{body}"
        print(f"[notify] 总览图已嵌入: {img_url}")
    if sector_url:
        body = f"![板块热度总览]({sector_url})\n\n{body}"
        print(f"[notify] 板块热度图已嵌入: {sector_url}")

    # 本地日志兜底 (始终写)
    log_path = _local_log(title, body)
    print(f"[notify] 本地日志 → {log_path}")

    sent = []
    if cfg.get("pushdeer_key") and _push_pushdeer(cfg["pushdeer_key"], title, body):
        sent.append("PushDeer")
    if cfg.get("serverchan_key") and _push_serverchan(cfg["serverchan_key"], title, body):
        sent.append("Server酱")
    if cfg.get("wecom_webhook"):
        if _push_wecom(cfg["wecom_webhook"], body):
            sent.append("企业微信")
            if sector_chart_path and os.path.exists(sector_chart_path):
                _push_wecom_image(cfg["wecom_webhook"], sector_chart_path)
            for code, png in (charts or {}).items():   # 推图
                _push_wecom_image(cfg["wecom_webhook"], png)

    if sent:
        print(f"[notify] 已推送: {', '.join(sent)}")
    elif not cfg:
        print("[notify] 未配置 config.json, 仅本地日志 "
              "(可填 pushdeer_key/serverchan_key/wecom_webhook 启用手机推送)")
    else:
        print("[notify] 所有远程渠道推送失败, 已存本地日志")


if __name__ == "__main__":
    # 自测: 用假数据
    demo = [{"code": "600868", "name": "梅雁吉祥", "price": 3.02, "SCR": 0.121,
             "套牢比例": 0.976, "峰数": 2, "主峰占比": 0.574,
             "verdict": "WEAK", "industry": "电力"}]
    send_daily(demo, demo, {})
