"""调度器 — 每日盘后自动运行筹码扫描漏斗 (APScheduler)。

计划:
  - 每个交易日 15:30  : 运行 orchestrator (Mid+High 筹码扫描 + 形态终审 + 通知)。
  - 每周五      16:00  : 先刷新全市场 universe (基础过滤), 再运行 orchestrator。

交易日判定: 周一~周五且非节假日 (简易版仅排除周末; 节假日可后续接日历)。
universe 刷新依赖东财 clist, 若被限流会自动沿用最近一次 universe CSV。

用法:
  python src/scheduler.py            # 前台常驻
  python src/scheduler.py --now      # 立即跑一次 (测试用)
"""

from __future__ import annotations

import argparse
import logging
import os
import subprocess
import sys
from datetime import datetime

from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger

SRC = os.path.dirname(__file__)
ROOT = os.path.dirname(SRC)
LOG_PATH = os.path.join(ROOT, "output", "scheduler.log")
sys.path.insert(0, SRC)
import orchestrator  # noqa: E402

os.makedirs(os.path.dirname(LOG_PATH), exist_ok=True)
_handlers: list[logging.Handler] = [logging.FileHandler(LOG_PATH, encoding="utf-8")]
if sys.stdout is not None:           # pythonw 下 stdout 为 None
    _handlers.append(logging.StreamHandler(sys.stdout))
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=_handlers,
)
log = logging.getLogger("scheduler")


def is_trading_day(d: datetime | None = None) -> bool:
    d = d or datetime.now()
    return d.weekday() < 5      # 0-4 = 周一~周五 (节假日暂未排除)


def refresh_universe() -> None:
    """跑 universe_filter (东财全市场), 限流失败不致命。"""
    log.info("刷新全市场 universe ...")
    try:
        subprocess.run([sys.executable, os.path.join(SRC, "universe_filter.py")],
                       check=False, timeout=900)
    except Exception as e:  # noqa: BLE001
        log.warning("universe 刷新失败 (将沿用旧快照): %s", e)


def daily_job() -> None:
    if not is_trading_day():
        log.info("非交易日, 跳过")
        return
    log.info("运行每日筹码扫描 ...")
    try:
        orchestrator.run(throttle=0.4, notify_enabled=True)
    except Exception as e:  # noqa: BLE001
        log.exception("orchestrator 异常: %s", e)


def friday_job() -> None:
    if not is_trading_day():
        return
    refresh_universe()
    daily_job()


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--now", action="store_true", help="立即跑一次后退出")
    args = ap.parse_args()

    if args.now:
        daily_job()
        return

    try:
        sched = BlockingScheduler(timezone="Asia/Shanghai")
        sched.add_job(daily_job, CronTrigger(day_of_week="mon-thu", hour=15,
                                             minute=30), id="daily")
        sched.add_job(friday_job, CronTrigger(day_of_week="fri", hour=16,
                                              minute=0), id="friday")
        log.info("调度器启动: 周一~四 15:30 扫描; 周五 16:00 刷新+扫描")
        sched.start()
    except (KeyboardInterrupt, SystemExit):
        log.info("已停止")
    except Exception as e:  # noqa: BLE001
        log.exception("调度器启动失败: %s", e)


if __name__ == "__main__":
    main()
