@echo off
title Agri Solutions Group - Discord Bot (Auto-Restart)
color 0A
chcp 65001 >nul
cd /d "%~dp0"

echo ===================================================
echo   🚜 AGRI SOLUTIONS GROUP DISCORD BOT
echo   Status: Starting bot with auto-restart...
echo ===================================================
echo.

:loop
echo [%date% %time%] Launching bot...
python main.py
echo.
echo [%date% %time%] ⚠️ Bot was stopped or closed. Restarting in 5 seconds...
echo (Press CTRL+C in this window to stop completely)
timeout /t 5 >nul
echo.
goto loop
