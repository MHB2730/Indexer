# One-command build for Indexer.
# Usage (from repo root, PowerShell):
#   .\build.ps1                 # full build: icons + exe + installer
#   .\build.ps1 -SkipInstaller  # stop after PyInstaller (no Inno Setup needed)
#
# Prerequisites:
#   * Python 3.11+ on PATH
#   * Inno Setup 6 installed (only if building the installer)

param(
    [switch]$SkipInstaller,
    [string]$InnoSetup = ""
)

function Find-InnoSetup {
    param([string]$Override)
    if ($Override -and (Test-Path $Override)) { return $Override }
    $candidates = @(
        "C:\Program Files (x86)\Inno Setup 6\ISCC.exe",
        "C:\Program Files\Inno Setup 6\ISCC.exe",
        "$env:LOCALAPPDATA\Programs\Inno Setup 6\ISCC.exe",
        "C:\Program Files (x86)\Inno Setup 5\ISCC.exe"
    )
    foreach ($c in $candidates) { if (Test-Path $c) { return $c } }
    $cmd = Get-Command iscc.exe -ErrorAction SilentlyContinue
    if ($cmd) { return $cmd.Source }
    return $null
}

$ErrorActionPreference = "Stop"
$Root = $PSScriptRoot

Write-Host ">>> Creating virtualenv" -ForegroundColor Cyan
if (-not (Test-Path "$Root\.venv")) {
    python -m venv "$Root\.venv"
}
$python = "$Root\.venv\Scripts\python.exe"

Write-Host ">>> Installing dependencies" -ForegroundColor Cyan
& $python -m pip install --upgrade pip
& $python -m pip install -r "$Root\requirements.txt"
& $python -m pip install pyside6 pillow pyinstaller

Write-Host ">>> Rendering brand icons" -ForegroundColor Cyan
& $python "$Root\scripts\make_icons.py"

Write-Host ">>> Building executable with PyInstaller" -ForegroundColor Cyan
$running = Get-Process Indexer -ErrorAction SilentlyContinue
if ($running) {
    Write-Warning "Indexer.exe is currently running. Stopping it so the build can proceed."
    $running | Stop-Process -Force
    Start-Sleep -Milliseconds 400
}
if (Test-Path "$Root\build") { Remove-Item "$Root\build" -Recurse -Force }
if (Test-Path "$Root\dist")  { Remove-Item "$Root\dist"  -Recurse -Force }
& $python -m PyInstaller "$Root\packaging\Indexer.spec" --clean --noconfirm

if ($SkipInstaller) {
    Write-Host "Build complete. App folder: dist\Indexer\" -ForegroundColor Green
    return
}

$iscc = Find-InnoSetup -Override $InnoSetup
if (-not $iscc) {
    Write-Warning "Inno Setup ISCC.exe was not found in any standard location. Searched:"
    Write-Warning "  C:\Program Files (x86)\Inno Setup 6\ISCC.exe"
    Write-Warning "  C:\Program Files\Inno Setup 6\ISCC.exe"
    Write-Warning "  $env:LOCALAPPDATA\Programs\Inno Setup 6\ISCC.exe"
    Write-Warning "Pass the path explicitly:  .\build.ps1 -InnoSetup 'D:\Path\To\ISCC.exe'"
    return
}

Write-Host ">>> Compiling installer with Inno Setup ($iscc)" -ForegroundColor Cyan
& $iscc "$Root\packaging\Indexer.iss"

Write-Host "Installer ready: packaging\Output\IndexerSetup.exe" -ForegroundColor Green
