@echo off
cd /d "%~dp0"
title Suzu ASCII Studio - 纯静态网页版
echo ======================================================
echo    Suzu ASCII Studio (纯静态 Web 版)
echo    正在启动本地静态服务并打开浏览器...
echo ======================================================

where python >nul 2>nul
if %errorlevel% equ 0 (
    start "" "http://127.0.0.1:8765"
    python -m http.server 8765
    goto :end
)

where node >nul 2>nul
if %errorlevel% equ 0 (
    start "" "http://127.0.0.1:8765"
    npx -y serve -l 8765 .
    goto :end
)

echo [提示] 未检测到 Python 或 Node.js，正在尝试直接用默认浏览器打开 index.html...
start "" "%~dp0index.html"

:end
