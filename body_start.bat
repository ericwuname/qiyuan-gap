@echo off
chcp 65001 >nul
cd /d "D:\0.个人文档\个人文档\启元智能"

echo.
echo ============================================
echo   启元智能 Body Daemon V2.1
echo   %date% %time%
echo ============================================
echo.

echo [预检1] 模块导入...
python -c "from body_daemon import check_loop; print('  OK body_daemon')" 2>nul
echo.

echo [预检2] suggested积压...
python brain\check_suggested.py 2>nul
echo.

echo [预检3] 推送管道...
python -c "import feishu_push; r=feishu_push.push('启元启动','守护进程已启动'); print('  feishu: ' + ('OK' if r.get('ok') else str(r.get('error','?')[:40])))" 2>nul
python -c "import email_push; r=email_push.send('启元启动','<h3>守护进程已启动</h3>'); print('  email: ' + ('OK' if r.get('ok') else str(r.get('error','?')[:40])))" 2>nul
echo.

echo [预检4] 当前状态...
python -c "import json; s=json.load(open('brain/body_state.json','r',encoding='utf-8')); print('  checks: ' + str(s.get('checks_completed',0)) + '  discoveries: ' + str(len(s.get('discoveries',[]))))" 2>nul
echo.

echo ============================================
echo   10分钟循环开始
echo   夜报: 22:00 飞书+邮件双推
echo   周检: 周一9-11时
echo   自愈: 每小时深度检查
echo   仪表盘: http://localhost:8080
echo   Ctrl+C 停止
echo ============================================
echo.

python brain\body_daemon.py
pause
