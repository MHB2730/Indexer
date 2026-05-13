"""PDF preview widget — renders the first page of a candidate file."""
from __future__ import annotations

from pathlib import Path

import fitz  # PyMuPDF
from PySide6.QtCore import Qt
from PySide6.QtGui import QImage, QPixmap
from PySide6.QtWidgets import QFrame, QLabel, QVBoxLayout


class PdfPreview(QFrame):
    """Frame that renders the first page of a PDF to a fitted QPixmap."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("PreviewFrame")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setStyleSheet(
            "QFrame#PreviewFrame { background:#FFFFFF; border:1px solid #E5E7EB;"
            " border-radius:10px; }"
        )
        self.setMinimumWidth(280)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)

        self.caption = QLabel("Preview")
        self.caption.setObjectName("FieldLabel")
        self.caption.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.caption)

        self.image_label = QLabel("Select an annexure to preview the matched file.")
        self.image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.image_label.setWordWrap(True)
        self.image_label.setStyleSheet("color:#64748B; font-size:12px;")
        layout.addWidget(self.image_label, 1)

        self._pixmap: QPixmap | None = None
        self._current_path: Path | None = None

    def clear(self) -> None:
        self._pixmap = None
        self._current_path = None
        self.caption.setText("Preview")
        self.image_label.setText("Select an annexure to preview the matched file.")
        self.image_label.setPixmap(QPixmap())

    def show_file(self, path: Path | None) -> None:
        if path is None:
            self.clear()
            return
        if path == self._current_path and self._pixmap is not None:
            self._rescale()
            return
        self._current_path = path
        self.caption.setText(path.name)
        suffix = path.suffix.lower()
        if suffix == ".pdf":
            self._pixmap = self._render_pdf_first_page(path)
        else:
            self._pixmap = None
        if self._pixmap is None or self._pixmap.isNull():
            self.image_label.setText(
                "Preview unavailable for this file type."
                if suffix != ".pdf"
                else "Could not render this PDF."
            )
            self.image_label.setPixmap(QPixmap())
        else:
            self._rescale()

    @staticmethod
    def _render_pdf_first_page(path: Path) -> QPixmap | None:
        try:
            with fitz.open(path) as doc:
                if doc.page_count == 0:
                    return None
                pix = doc[0].get_pixmap(dpi=120, alpha=False)
                img = QImage(pix.samples, pix.width, pix.height,
                             pix.stride, QImage.Format.Format_RGB888)
                return QPixmap.fromImage(img.copy())
        except Exception:
            return None

    def _rescale(self) -> None:
        if self._pixmap is None or self._pixmap.isNull():
            return
        avail = self.image_label.size()
        if avail.width() < 20 or avail.height() < 20:
            return
        scaled = self._pixmap.scaled(
            avail,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        self.image_label.setPixmap(scaled)

    def resizeEvent(self, event) -> None:  # noqa: D401, N802
        super().resizeEvent(event)
        self._rescale()
