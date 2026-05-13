# Fetch Tesseract OCR (Windows 64-bit) and stage it at vendor\tesseract\ so
# PyInstaller can bundle it into the Indexer installer.
#
# Strategy, in order of preference:
#   1. If tesseract.exe already at vendor\tesseract\, do nothing.
#   2. If choco is available, install via chocolatey (preinstalled on GHA
#      windows-latest), then copy the install tree.
#   3. If Tesseract is already installed system-wide, copy that tree.
#   4. Otherwise download the UB-Mannheim installer and install silently.

param(
    [string]$Version = "5.4.0.20240606",
    [string]$InstallerUrl = ""
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
$VendorDir = Join-Path $Root "vendor\tesseract"
$SystemPaths = @(
    "C:\Program Files\Tesseract-OCR",
    "C:\Program Files (x86)\Tesseract-OCR",
    (Join-Path $env:LOCALAPPDATA "Programs\Tesseract-OCR")
)

function Test-TesseractTree($dir) {
    return (Test-Path (Join-Path $dir "tesseract.exe")) `
        -and (Test-Path (Join-Path $dir "tessdata"))
}

function Copy-TesseractTree($src, $dst) {
    if (Test-Path $dst) { Remove-Item $dst -Recurse -Force }
    New-Item -ItemType Directory -Path $dst | Out-Null
    Copy-Item -Path (Join-Path $src "*") -Destination $dst -Recurse -Force
}

if (Test-TesseractTree $VendorDir) {
    Write-Host "Tesseract already staged at $VendorDir — skipping fetch."
    return
}

# 1. Look for an existing system-wide install.
foreach ($p in $SystemPaths) {
    if (Test-TesseractTree $p) {
        Write-Host "Found existing Tesseract at $p — copying to $VendorDir"
        Copy-TesseractTree $p $VendorDir
        return
    }
}

# 2. Try Chocolatey.
$choco = Get-Command choco -ErrorAction SilentlyContinue
if ($choco) {
    Write-Host "Installing Tesseract via Chocolatey..."
    & choco install tesseract --no-progress -y --force | Out-Host
    foreach ($p in $SystemPaths) {
        if (Test-TesseractTree $p) {
            Write-Host "Chocolatey installed Tesseract at $p — copying to $VendorDir"
            Copy-TesseractTree $p $VendorDir
            return
        }
    }
    Write-Warning "Chocolatey reported success but no install tree found in standard paths."
}

# 3. Direct download fallback.
if (-not $InstallerUrl) {
    $InstallerUrl = "https://digi.bib.uni-mannheim.de/tesseract/tesseract-ocr-w64-setup-$Version.exe"
}
$Tmp = Join-Path $env:TEMP "tesseract-installer-$Version.exe"
if (-not (Test-Path $Tmp)) {
    Write-Host "Downloading Tesseract $Version from $InstallerUrl ..."
    Invoke-WebRequest -Uri $InstallerUrl -OutFile $Tmp -UseBasicParsing
}

$Staging = Join-Path $env:TEMP "tesseract-stage-$Version"
if (Test-Path $Staging) { Remove-Item $Staging -Recurse -Force }
New-Item -ItemType Directory -Path $Staging | Out-Null

Write-Host "Installing Tesseract silently into $Staging ..."
$proc = Start-Process -FilePath $Tmp `
    -ArgumentList @(
        "/VERYSILENT", "/SUPPRESSMSGBOXES", "/NORESTART",
        "/SP-", "/NOICONS",
        "/DIR=`"$Staging`""
    ) -Wait -PassThru

if ($proc.ExitCode -ne 0) {
    throw "Tesseract installer exited with code $($proc.ExitCode)"
}
if (-not (Test-TesseractTree $Staging)) {
    throw "Installer did not produce a usable Tesseract tree in $Staging."
}

Copy-TesseractTree $Staging $VendorDir
Write-Host "Tesseract staged at $VendorDir."
