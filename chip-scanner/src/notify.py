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


def _build_text(recs: list[dict], passed: list[dict]) -> tuple[str, str]:
    """返回 (标题, markdown 正文)。"""
    ts = datetime.now().strftime("%Y-%m-%d %H:%M")
    n_pass = sum(1 for r in passed if r["verdict"] == "PASS")
    n_weak = sum(1 for r in passed if r["verdict"] == "WEAK")
    title = f"筹码扫描 {datetime.now():%m-%d}: {n_pass}个完美单峰 / {n_weak}个接近"

    lines = [f"## 筹码扫描结果 {ts}", ""]
    if not passed:
        lines.append("今日**无**完美/接近的低位单峰套牢盘。")
    else:
        lines.append("### 入选标的 (PASS=完美单峰, WEAK=主导单峰)")
        for r in passed:
            lines.append(
                f"- **[{r['verdict']}] {r['code']} {r['name']}** "
                f"现价{r['price']:.2f} | SCR={r['SCR']:.3f} | "
                f"套牢{r['套牢比例']:.0%} | 峰数{r['峰数']} | "
                f"主峰占比{r.get('主峰占比')} | {r.get('industry','')}")
    lines += ["", f"_High 池共 {len(recs)} 只, 完整见 high_pool CSV_"]
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
               charts: dict[str, str] | None = None) -> None:
    """发送每日通知。recs=全部High, passed=PASS/WEAK, charts={code:png}。"""
    cfg = _load_config()
    title, body = _build_text(recs, passed)

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
