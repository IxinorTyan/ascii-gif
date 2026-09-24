@echo off
cd /d "%~dp0"
python "scripts\start program.pyw"
if %errorlevel% neq 0 (
    echo.
    echo [ERROR] Program exited with error.
    pause
)
