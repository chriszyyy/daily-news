"""等待东财端点限流恢复后, 自动启动全量观察池扫描。

每 PROBE_INTERVAL 秒探测一次, 连续 2 次成功即认定恢复, 然后调用 watch_pool.main()。
"""

from __future__ import annotations

import subprocess
import sys
import time

sys.path.insert(0, "src")
import chip_calc  # noqa: E402

PROBE_INTERVAL = 150
MAX_WAIT_MIN = 180
PROBE_CODE = "000070"
INITIAL_COOLDOWN_SEC = 480   # 启动前先静默冷却, 让被封 IP 恢复


def main() -> None:
    print(f"[probe] 启动前静默冷却 {INITIAL_COOLDOWN_SEC}s ...", flush=True)
    time.sleep(INITIAL_COOLDOWN_SEC)

    t0 = time.time()
    while (time.time() - t0) < MAX_WAIT_MIN * 60:
        r = chip_calc.fetch_chip_latest(PROBE_CODE)
        if r is not None:
            print(f"[probe] 端点可用 ({r['code']} SCR={r['SCR']}), "
                  f"启动/续抓全量扫描 (节流 0.8s, 带缓存断点续抓)", flush=True)
            break
        mins = (time.time() - t0) / 60
        print(f"[probe] 仍限流, 已等待 {mins:.1f} 分钟", flush=True)
        time.sleep(PROBE_INTERVAL)
    else:
        print("[probe] 超时未恢复, 放弃", flush=True)
        return

    # 带缓存的全量扫描 (可重复运行, 自动跳过已缓存)
    subprocess.run([sys.executable, "src/watch_pool.py", "--throttle", "0.8"],
                   check=False)


if __name__ == "__main__":
    main()
