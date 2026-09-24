@echo off
cd /d "%~dp0"
python "studio\server.py"
if errorlevel 1 pause
