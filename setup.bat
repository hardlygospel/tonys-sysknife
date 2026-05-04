@echo off
REM Tony's Sysadmin Swiss Army Knife — Windows launcher

where python >nul 2>&1
if errorlevel 1 (
    echo [!] Python not found. Install from https://python.org
    pause
    exit /b 1
)

echo [*] Installing / upgrading dependencies...
python -m pip install --quiet --upgrade rich prompt_toolkit psutil requests

echo [*] Launching Tony's Sysadmin Swiss Army Knife...
python "%~dp0sysknife.py" %*
