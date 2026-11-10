@echo off
title Python Auto Clicker
cd /d "%~dp0"
python autoclicker.py
if %ERRORLEVEL% NEQ 0 (
    echo.
    echo An error occurred.
    pause
)
