# PyInstaller spec for the Indexer desktop app.
# Build:  pyinstaller packaging/Indexer.spec --clean --noconfirm
#
# Produces a one-folder distribution at dist/Indexer/.
# Inno Setup then wraps that folder into a Windows installer.

from pathlib import Path
from PyInstaller.utils.hooks import collect_submodules

PROJECT_ROOT = Path(SPECPATH).resolve().parent
SRC = PROJECT_ROOT / "src"
ASSETS = SRC / "indexer" / "assets"
VENDOR_TESS = PROJECT_ROOT / "vendor" / "tesseract"
VENDOR_EMB = PROJECT_ROOT / "vendor" / "embedding-model"

hidden = collect_submodules("rank_bm25") + collect_submodules("rapidfuzz")

a = Analysis(
    [str(PROJECT_ROOT / "packaging" / "launcher.py")],
    pathex=[str(SRC)],
    binaries=[],
    datas=(
        [(str(ASSETS), "indexer/assets")]
        + ([(str(VENDOR_TESS), "tesseract")] if VENDOR_TESS.is_dir() else [])
        + ([(str(VENDOR_EMB), "embedding-model")] if VENDOR_EMB.is_dir() else [])
    ),
    hiddenimports=hidden,
    hookspath=[],
    runtime_hooks=[],
    excludes=["tkinter", "test", "unittest"],
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="Indexer",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    icon=str(ASSETS / "icon.ico"),
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="Indexer",
)
