# One-time setup for Music Download Agent
# ALL installs/caches go under this project folder (avoid full C: drive)
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

Write-Host "=== Music Download Agent setup ===" -ForegroundColor Cyan
Write-Host "Project: $PSScriptRoot"
Write-Host "All downloads stay in this folder (not C:)." -ForegroundColor Yellow

# Local dirs on project drive
$music     = Join-Path $PSScriptRoot "Music"
$cache     = Join-Path $PSScriptRoot ".cache"
$browsers  = Join-Path $PSScriptRoot ".playwright-browsers"
$pipCache  = Join-Path $cache "pip"
$tmpDir    = Join-Path $cache "tmp"

foreach ($d in @($music, $cache, $browsers, $pipCache, $tmpDir)) {
    if (-not (Test-Path $d)) {
        New-Item -ItemType Directory -Path $d | Out-Null
    }
}

# Force every tool off C:
$env:PLAYWRIGHT_BROWSERS_PATH = $browsers
$env:PIP_CACHE_DIR            = $pipCache
$env:TEMP                     = $tmpDir
$env:TMP                      = $tmpDir
$env:TMPDIR                   = $tmpDir
$env:XDG_CACHE_HOME           = $cache

Write-Host "PLAYWRIGHT_BROWSERS_PATH = $env:PLAYWRIGHT_BROWSERS_PATH"
Write-Host "PIP_CACHE_DIR            = $env:PIP_CACHE_DIR"
Write-Host "TEMP/TMP                 = $env:TEMP"

# Virtual environment (already on E: if project is on E:)
$venv = Join-Path $PSScriptRoot ".venv"
if (-not (Test-Path $venv)) {
    Write-Host "Creating virtual environment..."
    python -m venv $venv
}

$py  = Join-Path $venv "Scripts\python.exe"
$pip = Join-Path $venv "Scripts\pip.exe"

Write-Host "Upgrading pip..."
& $py -m pip install --upgrade pip --cache-dir $pipCache

Write-Host "Installing Python packages (yt-dlp, playwright)..."
& $pip install -r (Join-Path $PSScriptRoot "requirements.txt") --cache-dir $pipCache

Write-Host "Installing Playwright Chromium into project folder..."
& $py -m playwright install chromium

# Quick checks
Write-Host ""
Write-Host "Checking tools..." -ForegroundColor Cyan
& $py -c "import yt_dlp; print('yt-dlp OK', yt_dlp.version.__version__)"
& $py -c "from playwright.sync_api import sync_playwright; print('playwright OK')"

$chrome = Get-ChildItem -Path $browsers -Recurse -Filter "chrome.exe" -ErrorAction SilentlyContinue | Select-Object -First 1
if ($chrome) {
    Write-Host "Chromium OK: $($chrome.FullName)"
} else {
    Write-Host "WARNING: chrome.exe not found under .playwright-browsers" -ForegroundColor Yellow
}

$ffmpeg = Get-Command ffmpeg -ErrorAction SilentlyContinue
if ($ffmpeg) {
    Write-Host "ffmpeg OK: $($ffmpeg.Source)"
} else {
    Write-Host "WARNING: ffmpeg not found on PATH. yt-dlp MP3 conversion needs ffmpeg." -ForegroundColor Yellow
    Write-Host "  Prefer installing ffmpeg onto E: if C: is full."
}

Write-Host ""
Write-Host "Setup complete." -ForegroundColor Green
Write-Host "Run:  .\start.bat"
Write-Host ""
Write-Host "Optional env vars:"
Write-Host "  HEADLESS=0     show browser while using ytmp3vid"
Write-Host "  SKIP_YTMP3=1   use yt-dlp only"
