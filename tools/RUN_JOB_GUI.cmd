@echo off
cd /d "%~dp0\.."
echo Opening Job Battery GUI...
pythonw "%~dp0job_battery_gui.py" 2>nul
if errorlevel 1 python "%~dp0job_battery_gui.py"
if errorlevel 1 (
  echo Python failed. Try: py "%~dp0job_battery_gui.py"
  pause
)
