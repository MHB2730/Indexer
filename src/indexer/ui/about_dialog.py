"""About dialog — version, links, OCR/Word availability status."""
from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QDesktopServices, QPixmap
from PySide6.QtWidgets import (
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
)

from .. import __version__
from ..logging_setup import log_dir
from ..embedder import MODEL_NAME, is_available as embedder_available
from ..ocr import is_available as tesseract_available, tesseract_path


ASSETS = Path(__file__).resolve().parent.parent / "assets"
GITHUB_URL = "https://github.com/MHB2730/Indexer"
RELEASES_URL = f"{GITHUB_URL}/releases"


class AboutDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("About Indexer")
        self.setModal(True)
        self.setMinimumSize(480, 460)
        self.setObjectName("AboutDialog")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setStyleSheet("QDialog#AboutDialog { background:#F4F5F9; }")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 24, 28, 20)
        layout.setSpacing(14)

        # Header
        header = QHBoxLayout()
        header.setSpacing(14)
        logo = QLabel()
        png = ASSETS / "icon.png"
        if png.exists():
            logo.setPixmap(QPixmap(str(png)).scaled(
                72, 72,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            ))
        header.addWidget(logo)

        title_box = QVBoxLayout()
        title_box.setSpacing(2)
        name = QLabel("Indexer")
        name.setObjectName("H1")
        tagline = QLabel("Legal Bundle Assembler")
        tagline.setObjectName("FieldLabel")
        version = QLabel(f"Version {__version__}")
        version.setObjectName("Sub")
        title_box.addWidget(name)
        title_box.addWidget(tagline)
        title_box.addWidget(version)
        header.addLayout(title_box, 1)
        layout.addLayout(header)

        # Capability panel
        caps = QFrame()
        caps.setObjectName("Card")
        caps.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        caps.setStyleSheet(
            "QFrame#Card { background:#FFFFFF; border:1px solid #E5E7EB;"
            " border-radius:10px; }"
        )
        cl = QVBoxLayout(caps)
        cl.setContentsMargins(18, 14, 18, 14)
        cl.setSpacing(6)

        cl.addWidget(self._cap_row(
            f"Semantic matching ({MODEL_NAME})",
            embedder_available(),
            "Embeddings used to rank candidate files by meaning, not just keywords.",
        ))
        cl.addWidget(self._cap_row(
            "Optical Character Recognition (Tesseract)",
            tesseract_available(),
            "Used to read scanned PDFs without a text layer.",
            detail=tesseract_path() or "",
        ))
        cl.addWidget(self._cap_row(
            "DOCX → PDF conversion (Microsoft Word)",
            _word_available(),
            "Used to include DOCX main documents in the merged bundle.",
        ))
        layout.addWidget(caps)

        # Description
        desc = QLabel(
            "Indexer runs entirely on your computer. No documents leave your "
            "machine — all processing, indexing, and matching is local. "
            "Updates are downloaded from GitHub Releases."
        )
        desc.setWordWrap(True)
        desc.setStyleSheet("color:#475569; font-size:12px;")
        layout.addWidget(desc)

        # Log location
        log_path = log_dir() / "indexer.log"
        log_label = QLabel(f"Log file: <code>{log_path}</code>")
        log_label.setTextFormat(Qt.TextFormat.RichText)
        log_label.setStyleSheet("color:#475569; font-size:11px;")
        log_label.setWordWrap(True)
        layout.addWidget(log_label)

        layout.addStretch(1)

        # Buttons
        row = QHBoxLayout()
        gh = QPushButton("View on GitHub")
        gh.clicked.connect(lambda: QDesktopServices.openUrl(QUrl(GITHUB_URL)))
        rel = QPushButton("Latest releases")
        rel.clicked.connect(lambda: QDesktopServices.openUrl(QUrl(RELEASES_URL)))
        close = QPushButton("Close")
        close.setObjectName("Primary")
        close.setMinimumHeight(36)
        close.clicked.connect(self.accept)
        row.addWidget(gh)
        row.addWidget(rel)
        row.addStretch(1)
        row.addWidget(close)
        layout.addLayout(row)

    @staticmethod
    def _cap_row(title: str, ok: bool, hint: str, detail: str = "") -> QFrame:
        f = QFrame()
        h = QHBoxLayout(f)
        h.setContentsMargins(0, 0, 0, 0)
        h.setSpacing(10)

        dot = QLabel("●")
        dot.setFixedWidth(14)
        dot.setStyleSheet(
            f"color:{'#2F855A' if ok else '#B45309'}; font-size:14px;"
        )
        h.addWidget(dot)

        text_box = QVBoxLayout()
        text_box.setSpacing(0)
        t = QLabel(title)
        t.setStyleSheet("color:#0F172A; font-weight:600; font-size:12px;")
        text_box.addWidget(t)
        status_line = (
            "Available" + (f" — {detail}" if detail else "") if ok
            else "Not detected — " + hint
        )
        s = QLabel(status_line)
        s.setStyleSheet("color:#64748B; font-size:11px;")
        s.setWordWrap(True)
        text_box.addWidget(s)
        h.addLayout(text_box, 1)
        return f


def _word_available() -> bool:
    """Lightweight check: docx2pdf imports + Word COM available."""
    try:
        import docx2pdf  # noqa: F401
    except ImportError:
        return False
    try:
        import win32com.client  # type: ignore
        try:
            obj = win32com.client.Dispatch("Word.Application")
            obj.Quit()
            return True
        except Exception:
            return False
    except ImportError:
        # Without win32com we can't probe; assume yes if docx2pdf imported.
        return True
