@echo off
cd /d "%~dp0\.."
echo Running LinkedIn battery (no Cursor needed)...
powershell -ExecutionPolicy Bypass -File "%~dp0linkedin_battery.ps1"
echo.
pause
