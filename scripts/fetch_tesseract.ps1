# Fetch Tesseract OCR (Windows 64-bit) and stage it at vendor\tesseract\ so
# PyInstaller can bundle it into the Indexer installer.
#
# Strategy:
#   1. If vendor\tesseract\tesseract.exe already exists, do nothing.
#   2. Otherwise, install the official UB-Mannheim Tesseract installer
#      silently into vendor\tesseract\ (it's an Inno Setup installer so
#      /VERYSILENT /DIR= works).
#
# The download URL points at the long-term-stable UB-Mannheim mirror.

param(
    [string]$Version = "5.4.0.20240606",
    [string]$InstallerUrl = ""
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
$VendorDir = Join-Path $Root "vendor\tesseract"
$Exe = Join-Path $VendorDir "tesseract.exe"

if (Test-Path $Exe) {
    Write-Host "Tesseract already present at $VendorDir — skipping fetch."
    return
}

if (-not $InstallerUrl) {
    $InstallerUrl = "https://digi.bib.uni-mannheim.de/tesseract/tesseract-ocr-w64-setup-$Version.exe"
}

$Tmp = Join-Path $env:TEMP "tesseract-installer-$Version.exe"

if (-not (Test-Path $Tmp)) {
    Write-Host "Downloading Tesseract $Version from $InstallerUrl ..."
    Invoke-WebRequest -Uri $InstallerUrl -OutFile $Tmp -UseBasicParsing
}

if (Test-Path $VendorDir) {
    Remove-Item $VendorDir -Recurse -Force
}
New-Item -ItemType Directory -Path $VendorDir | Out-Null

Write-Host "Installing Tesseract silently to $VendorDir ..."
$proc = Start-Process -FilePath $Tmp `
    -ArgumentList @(
        "/VERYSILENT", "/SUPPRESSMSGBOXES", "/NORESTART",
        "/DIR=`"$VendorDir`"",
        "/TASKS=`"`"",
        "/COMPONENTS=`"!shortcuts`""
    ) -Wait -PassThru

if ($proc.ExitCode -ne 0) {
    throw "Tesseract installer exited with code $($proc.ExitCode)"
}

if (-not (Test-Path $Exe)) {
    throw "Tesseract installation did not produce $Exe. Inspect $VendorDir."
}

Write-Host "Tesseract staged at $VendorDir."
