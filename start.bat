@echo off
chcp 65001 >nul
setlocal
cd /d "%~dp0"
set PYTHONIOENCODING=utf-8
set PYTHONUTF8=1

rem Keep Playwright / temp / caches on this project drive (not C:)
set "PLAYWRIGHT_BROWSERS_PATH=%~dp0.playwright-browsers"
set "PIP_CACHE_DIR=%~dp0.cache\pip"
set "TEMP=%~dp0.cache\tmp"
set "TMP=%~dp0.cache\tmp"
set "TMPDIR=%~dp0.cache\tmp"
set "XDG_CACHE_HOME=%~dp0.cache"

if not exist "%~dp0.cache\tmp" mkdir "%~dp0.cache\tmp"
if not exist "%~dp0Music" mkdir "%~dp0Music"
if not exist "%~dp0.playwright-browsers" mkdir "%~dp0.playwright-browsers"

rem Check if virtual environment exists. If not, auto-run setup.ps1
if not exist "%~dp0.venv\Scripts\python.exe" (
  echo [!] Virtual environment ^(.venv^) not found.
  echo [*] Auto-running setup.ps1 to install required dependencies...
  echo.
  powershell -ExecutionPolicy Bypass -File "%~dp0setup.ps1"
  if errorlevel 1 (
    echo.
    echo [X] Setup failed. Please check your Python installation and internet connection.
    echo.
    pause
    exit /b 1
  )
)

rem Run agent.py using .venv Python
"%~dp0.venv\Scripts\python.exe" "%~dp0agent.py" %*
if errorlevel 1 (
  echo.
  echo [!] Application closed due to an error above.
  echo.
  pause
)

endlocal

