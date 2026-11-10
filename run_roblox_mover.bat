@echo off
title Roblox Auto Mover
cd /d "%~dp0"
python roblox_mover.py
if %ERRORLEVEL% NEQ 0 (
    echo.
    echo An error occurred.
    pause
)
