@echo off
title 字符画转换器 Ascii Converter
cd /d "%~dp0"
python "scripts\start program.pyw"
if %errorlevel% neq 0 (
    echo.
    echo [提示] 程序退出或出错，错误码: %errorlevel%
    pause
)