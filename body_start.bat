@echo off
chcp 65001 >nul
REM 启元智能 · Body Daemon V2 · 启动脚本
REM 10分钟自检循环，后台运行

cd /d "D:\0.个人文档\个人文档\启元智能"

echo.
echo ============================================
echo   启元智能 · Body Daemon V2
echo   启动时间: %date% %time%
echo ============================================
echo.

REM 快速健康检查
echo [预检] 快速健康扫描...
python brain\check_suggested.py 2>nul
if errorlevel 1 (
    echo [WARN] check_suggested 异常
)

echo.
echo [预检] 模块导入检查...
python -c "from body_daemon import check_loop; print('[OK] body_daemon 可导入')" 2>nul
if errorlevel 1 (
    echo [FAIL] body_daemon 导入失败，请检查代码
    pause
    exit /b 1
)

echo.
echo [预检] 当前状态:
python -c "import json; s=json.load(open('brain/body_state.json','r',encoding='utf-8')); print(f'  checks: {s.get(\"checks_completed\",0)}'); print(f'  discoveries: {len(s.get(\"discoveries\",[]))}'); cv2=s.get('_curiosity_v2',{}); print(f'  curiosity: phase={cv2.get(\"phase\",\"?\")} oq={cv2.get(\"open_questions\",\"?\")} heavy={cv2.get(\"heavy_items\",\"?\")}'); print(f'  suggested overflow: {s.get(\"_last_suggested_overflow_alert\",\"none\")}')" 2>nul

echo.
echo ============================================
echo   开始10分钟守护循环...
echo   按 Ctrl+C 停止
echo   夜报: 每日22:00自动生成 body_logs/night_brief_*.md
echo   周检: 每周一9-11点自动提醒 suggested 审核
echo ============================================
echo.

python brain\body_daemon.py

pause
