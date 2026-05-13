"""Optional OCR via locally-installed Tesseract.

Tesseract is not bundled in v0.1.x — we look for an existing install in
the standard locations and on PATH. If found, OCR is applied to pages
that produced little or no extractable text (likely scanned). If not
found, OCR is silently skipped and the caller continues with whatever
text the PDF parser managed to pull out.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import fitz  # PyMuPDF

_CANDIDATE_PATHS = [
    r"C:\Program Files\Tesseract-OCR\tesseract.exe",
    r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
    os.path.expandvars(r"%LOCALAPPDATA%\Programs\Tesseract-OCR\tesseract.exe"),
]


def _bundled_tesseract() -> Path | None:
    """Path to a Tesseract binary that ships with this Indexer install, if any.

    In a PyInstaller bundle, data files live under sys._MEIPASS. In a dev
    checkout, we keep a copy at <repo>/vendor/tesseract/.
    """
    if hasattr(sys, "_MEIPASS"):
        base = Path(sys._MEIPASS) / "tesseract"
    else:
        base = Path(__file__).resolve().parents[2] / "vendor" / "tesseract"
    exe = base / "tesseract.exe"
    return exe if exe.is_file() else None

# Pages whose extracted text falls below this length are considered "likely
# scanned" and re-processed with OCR.
MIN_TEXT_LEN_PER_PAGE = 60


_tesseract_cmd: str | None = None
_searched = False


def tesseract_path() -> str | None:
    """Return absolute path to tesseract.exe — bundled, on PATH, or installed."""
    global _tesseract_cmd, _searched
    if _searched:
        return _tesseract_cmd
    _searched = True

    bundled = _bundled_tesseract()
    if bundled:
        _tesseract_cmd = str(bundled)
        return _tesseract_cmd

    found = shutil.which("tesseract")
    if found:
        _tesseract_cmd = found
        return _tesseract_cmd

    for p in _CANDIDATE_PATHS:
        if p and Path(p).is_file():
            _tesseract_cmd = p
            return _tesseract_cmd

    return None


def _tessdata_env(tess_exe: str) -> dict:
    """Build a subprocess env that points TESSDATA_PREFIX at the right folder."""
    env = os.environ.copy()
    tess_dir = Path(tess_exe).parent
    candidate = tess_dir / "tessdata"
    if candidate.is_dir():
        env["TESSDATA_PREFIX"] = str(candidate)
    return env


def is_available() -> bool:
    return tesseract_path() is not None


def ocr_page(page: fitz.Page, dpi: int = 220) -> str:
    """Rasterise a PDF page and OCR it. Returns "" if Tesseract unavailable."""
    tess = tesseract_path()
    if not tess:
        return ""

    pix = page.get_pixmap(dpi=dpi, alpha=False)
    with tempfile.TemporaryDirectory() as tmp:
        img_path = Path(tmp) / "page.png"
        out_base = Path(tmp) / "out"
        pix.save(str(img_path))
        try:
            subprocess.run(
                [tess, str(img_path), str(out_base), "-l", "eng", "--psm", "3"],
                check=True,
                capture_output=True,
                timeout=60,
                env=_tessdata_env(tess),
            )
        except (subprocess.SubprocessError, OSError):
            return ""
        txt_file = out_base.with_suffix(".txt")
        if not txt_file.exists():
            return ""
        return txt_file.read_text(encoding="utf-8", errors="ignore")
