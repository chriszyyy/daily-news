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

    lines = [f"## 筹码扫描结果 {ts}", "",
             "盈利 + 单峰密集 (120日窗口, 按带宽升序)", ""]
    if hot_sectors:
        lines += ["### 今日热门板块", " / ".join(hot_sectors[:8]), ""]
    if not passed:
        lines.append("今日**无**符合条件的单峰密集标的。")
    else:
        lines.append("### 入选标的")
        lines.append("> 格式: 形态(带宽/次峰比/距主峰) · 资金(主力/超大单/大单) · 基本面 · 量价")
        lines.append("")
        for i, r in enumerate(passed, 1):
            def _f(v, suf="%"):
                return f"{v:+.0f}{suf}" if isinstance(v, (int, float)) else "—"
            np_yoy = _f(r.get("净利润同比"))
            rev_yoy = _f(r.get("营收同比"))
            roe = (f"{r['ROE']:.1f}%" if isinstance(r.get("ROE"), (int, float))
                   else "—")
            vr = (f"{r['量比']:.1f}" if isinstance(r.get("量比"), (int, float))
                  else "—")
            amt = (f"{r['成交额亿']:.1f}亿"
                   if isinstance(r.get("成交额亿"), (int, float)) else "—")
            main = (f"{r['主力净流入亿']:+.2f}亿/{r.get('主力净占比'):+.1f}%"
                    if isinstance(r.get("主力净流入亿"), (int, float))
                    and isinstance(r.get("主力净占比"), (int, float)) else "—")
            super_flow = (f"{r['超大单净流入亿']:+.2f}亿"
                          if isinstance(r.get("超大单净流入亿"), (int, float))
                          else "—")
            large = (f"{r['大单净流入亿']:+.2f}亿"
                     if isinstance(r.get("大单净流入亿"), (int, float)) else "—")
            fund_mark = "✓" if r.get("资金确认") == "是" else "—"
            lines.append(
                f"**{i}. {r['code']} {r['name']}** ({r.get('industry','')}) "
                f"现价{r['price']:.2f} PE{r['PE']:.0f}\n"
                f"　形态: 带宽{r['带宽70']:.0%}/次峰{r['次峰比']:.2f}/距峰{r['距主峰']:+.0%} "
                f"· 资金{fund_mark}: 主力{main}/超大{super_flow}/大单{large} "
                f"· 业绩: 净利{np_yoy}/营收{rev_yoy}/ROE{roe} "
                f"· 量价: 量比{vr}/额{amt}")
    trend_recs = trend_recs or []
    if trend_recs:
        lines += ["", "### 强趋势启动池"]
        lines.append("> 补充捕捉已脱离横盘、正在发动的趋势票；不要求单峰密集。")
        lines.append("")
        for i, r in enumerate(trend_recs, 1):
            breakout = "新高" if r.get("突破20日新高") else "近高"
            ma = "多头" if r.get("均线多头") else "站上MA20"
            pe = f"{r.get('PE'):.0f}" if isinstance(r.get("PE"), (int, float)) else "—"
            lines.append(
                f"**T{i}. {r['code']} {r['name']}** ({r.get('industry','')}) "
                f"现价{r['现价']:.2f} PE{pe}\n"
                f"　趋势: {r.get('趋势档位','')} 5日{r['近5日涨幅']:+.1f}%/20日{r['近20日涨幅']:+.1f}% "
                f"· {breakout} {r['接近20日高点']:.0%} · {ma} · {r.get('入选原因')} "
                f"· 过热{r.get('过热风险','否')} "
                f"· 量价: 放量比{r.get('放量比')}/额{r.get('成交额亿')}亿 "
                f"· 分{r.get('趋势分')}")

    push_recs = push_recs or []
    if push_recs:
        lines += ["", "### 推盘观察池"]
        lines.append("> 仅提示资金推价痕迹，不作为买入建议；高位/过热默认只观察。")
        lines.append("")
        for i, r in enumerate(push_recs, 1):
            lines.append(
                f"**P{i}. {r['code']} {r['name']}** ({r.get('industry','')}) "
                f"现价{r['现价']:.2f}\n"
                f"　观察: {r.get('推盘档位')} / 风险{r.get('风险分层')} "
                f"· 主力{r['主力净流入亿']:+.2f}亿/{r['主力净占比']:+.1f}% "
                f"· 超大{r['超大单净流入亿']:+.2f}亿/大单{r['大单净流入亿']:+.2f}亿 "
                f"· 强度{r['收盘强度']:.0%} · 5日{r['近5日涨幅']:+.1f}%/20日{r['近20日涨幅']:+.1f}% "
                f"· 分{r.get('推盘分')}")

    lines += ["", f"_完整见 high_pool / trend_pool / push_pool CSV_"]
    return title, "\n".join(lines)


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
        r = requests.post(f"https://sctapi.ftqq.com/{key}.send",
                          data={"title": title, "desp": body}, timeout=10)
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
               push_recs: list[dict] | None = None) -> None:
    """发送每日通知。recs=全部High, passed=入选, overview_path=总览图本地路径。"""
    cfg = _load_config()
    title, body = _build_text(recs, passed, trend_recs=trend_recs,
                              hot_sectors=hot_sectors, push_recs=push_recs)

    # 总览图: push 到公开仓库, 取 jsDelivr CDN URL, 嵌入 Markdown
    img_url = None
    if overview_path:
        try:
            import git_image
            img_url = git_image.upload_image(overview_path)
        except Exception as e:  # noqa: BLE001
            print(f"[notify] 图床上传失败: {e}")
    if img_url:
        body = f"![单峰密集总览]({img_url})\n\n{body}"
        print(f"[notify] 总览图已嵌入: {img_url}")

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
