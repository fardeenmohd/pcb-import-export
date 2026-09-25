@echo off
:: Change directory to the location of the script
cd /d "%~dp0"

:: Run the application without a persistent console window
start "" "venv\Scripts\pythonw.exe" "main.py"
