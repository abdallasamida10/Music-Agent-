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

if exist "%~dp0.venv\Scripts\python.exe" (
  "%~dp0.venv\Scripts\python.exe" "%~dp0agent.py" %*
) else (
  where py >nul 2>&1 && (
    py -3 "%~dp0agent.py" %*
  ) || (
    python "%~dp0agent.py" %*
  )
)

echo.
pause
endlocal
