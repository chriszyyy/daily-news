"""把总览图推到公开 GitHub 仓库, 返回 jsDelivr CDN URL (国内可达, 微信能抓)。

策略 (仓库不膨胀):
  - 固定文件 chip-scanner/pushimg/latest.png, 覆盖式 commit。
  - 返回 jsDelivr URL (带时间戳破缓存)。

依赖: 本地 git 已配置 credential (push 免密); 仓库为 public。
"""

from __future__ import annotations

import os
import shutil
import subprocess
import time

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))  # daily-news
PUSH_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "pushimg")
# jsDelivr CDN (国内可达, 微信可抓); @latest 不缓存太久, 用 commit 后稳定
CDN_BASE = ("https://cdn.jsdelivr.net/gh/chriszyyy/daily-news@master/"
            "chip-scanner/pushimg/latest.png")


def _git(*args, timeout=120) -> tuple[int, str]:
    p = subprocess.run(["git", *args], cwd=REPO_ROOT, capture_output=True,
                       text=True, timeout=timeout)
    return p.returncode, (p.stdout + p.stderr).strip()


def upload_image(src_path: str, name: str = "latest") -> str | None:
    """复制为 pushimg/{name}.png 并 push。返回 jsDelivr URL (带 SHA 破缓存)。

    name 区分不同用途图 (latest=筹码总览, sector=板块热度), 各自固定文件不膨胀。
    """
    if not os.path.exists(src_path):
        return None
    os.makedirs(PUSH_DIR, exist_ok=True)
    dst = os.path.join(PUSH_DIR, f"{name}.png")
    shutil.copyfile(src_path, dst)

    rel = os.path.relpath(dst, REPO_ROOT).replace("\\", "/")
    code, out = _git("add", rel)
    if code != 0:
        print(f"[gitimg] add 失败: {out}")
        return None
    _git("commit", "-m", f"chore: update push {name} image")  # 无变化容忍
    code, out = _git("push", "origin", "HEAD")
    if code != 0 and "up-to-date" not in out.lower():
        print(f"[gitimg] push 失败: {out}")
        return None
    # 用 commit SHA 锁定版本 (jsDelivr 对 SHA 永久缓存且即时, 避免 @master 旧缓存)
    sha_code, sha = _git("rev-parse", "HEAD")
    sha = sha.strip()[:40] if sha_code == 0 else "master"
    return (f"https://cdn.jsdelivr.net/gh/chriszyyy/daily-news@{sha}/"
            f"chip-scanner/pushimg/{name}.png")


if __name__ == "__main__":
    import sys
    src = sys.argv[1] if len(sys.argv) > 1 else None
    print(upload_image(src) if src else "用法: python git_image.py <图片路径>")
