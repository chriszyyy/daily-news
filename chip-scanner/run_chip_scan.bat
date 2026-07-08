@echo off
REM ── 每日盘后筹码扫描 (Windows 计划任务 Daily 触发, 跑完即退) ──
set "PY=C:\Users\yizhang6\AppData\Local\Programs\Python\Python312\python.exe"
set "ROOT=%~dp0"
set "PYTHONUTF8=1"
set "PYTHONIOENCODING=utf-8"
cd /d "%ROOT%"
echo [%date% %time%] chip-scan start >> "%ROOT%output\task_chip_scan.log"
"%PY%" "%ROOT%src\scheduler.py" --now >> "%ROOT%output\task_chip_scan.log" 2>&1
echo [%date% %time%] chip-scan end (exit=%ERRORLEVEL%) >> "%ROOT%output\task_chip_scan.log"
