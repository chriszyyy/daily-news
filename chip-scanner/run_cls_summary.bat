@echo off
REM ── 每日收盘后财联社快讯汇总推送 (Windows 计划任务 Daily 触发, 跑完即退) ──
set "PY=C:\Users\yizhang6\AppData\Local\Programs\Python\Python312\python.exe"
set "ROOT=%~dp0"
set "PYTHONUTF8=1"
set "PYTHONIOENCODING=utf-8"
cd /d "%ROOT%"
echo [%date% %time%] cls-summary start >> "%ROOT%output\task_cls_summary.log"
"%PY%" "%ROOT%src\cls_telegraph.py" --once --rn 50 >> "%ROOT%output\task_cls_summary.log" 2>&1
echo [%date% %time%] cls-summary end (exit=%ERRORLEVEL%) >> "%ROOT%output\task_cls_summary.log"
