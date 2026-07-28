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
if (Test-Path $venvPython) {
    & $venvPython (Join-Path $PSScriptRoot "agent.py") @args
} else {
    python (Join-Path $PSScriptRoot "agent.py") @args
}

Write-Host ""
Read-Host -Prompt "Press Enter to exit..."
