# Music Download Agent launcher — all paths stay in project folder
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
[Console]::InputEncoding = [System.Text.Encoding]::UTF8
$env:PYTHONIOENCODING = "utf-8"
$env:PYTHONUTF8 = "1"

# Keep Playwright / temp / caches on this project drive (not C:)
$env:PLAYWRIGHT_BROWSERS_PATH = Join-Path $PSScriptRoot ".playwright-browsers"
$env:PIP_CACHE_DIR            = Join-Path $PSScriptRoot ".cache\pip"
$env:TEMP                     = Join-Path $PSScriptRoot ".cache\tmp"
$env:TMP                      = $env:TEMP
$env:TMPDIR                   = $env:TEMP
$env:XDG_CACHE_HOME           = Join-Path $PSScriptRoot ".cache"

foreach ($d in @(
    $env:PLAYWRIGHT_BROWSERS_PATH,
    $env:PIP_CACHE_DIR,
    $env:TEMP,
    (Join-Path $PSScriptRoot "Music")
)) {
    if (-not (Test-Path $d)) { New-Item -ItemType Directory -Path $d | Out-Null }
}

$venvPython = Join-Path $PSScriptRoot ".venv\Scripts\python.exe"

if (-not (Test-Path $venvPython)) {
    Write-Host "[!] Virtual environment (.venv) not found on this machine." -ForegroundColor Yellow
    Write-Host "[*] Running setup.ps1 automatically to install dependencies..." -ForegroundColor Cyan
    & (Join-Path $PSScriptRoot "setup.ps1")
}

if (Test-Path $venvPython) {
    & $venvPython (Join-Path $PSScriptRoot "agent.py") @args
    if ($LASTEXITCODE -ne 0) {
        Write-Host ""
        Write-Host "[!] Application exited with error code $LASTEXITCODE." -ForegroundColor Red
        Read-Host "Press Enter to exit..."
    }
} else {
    Write-Host "[X] Could not find Python virtual environment. Please run setup.ps1 manually." -ForegroundColor Red
    Read-Host "Press Enter to exit..."
}
