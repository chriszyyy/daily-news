@echo off
REM ── 每日收盘后财联社次日候选 + 前向验证 (Windows 计划任务 Daily, 跑完即退) ──
set "PY=C:\Users\yizhang6\AppData\Local\Programs\Python\Python312\python.exe"
set "ROOT=%~dp0"
set "PYTHONUTF8=1"
set "PYTHONIOENCODING=utf-8"
cd /d "%ROOT%"
echo [%date% %time%] cls-signal start >> "%ROOT%output\task_cls_signal.log"
"%PY%" "%ROOT%src\cls_signal.py" --daily >> "%ROOT%output\task_cls_signal.log" 2>&1
echo [%date% %time%] cls-signal end (exit=%ERRORLEVEL%) >> "%ROOT%output\task_cls_signal.log"
