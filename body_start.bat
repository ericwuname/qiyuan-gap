@echo off
REM 启元智能 · 身体守护进程 启动脚本
REM 后台运行，10分钟自检循环

cd /d "D:\0.个人文档\个人文档\启元智能"

echo.
echo ============================================
echo   启元智能 · Body Daemon
echo   启动中...
echo ============================================
echo.

python brain\body_daemon.py

pause
