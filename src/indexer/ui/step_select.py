"""Step 1: select the main document and the candidate pool."""
from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from .widgets import Card


ASSETS = Path(__file__).resolve().parent.parent / "assets"


class SelectStep(QWidget):
    proceed = Signal(Path, Path, Path)

    def __init__(self, parent=None):
        super().__init__(parent)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(56, 44, 56, 36)
        outer.setSpacing(22)

        # ── Hero ──────────────────────────────────────────────
        hero = QHBoxLayout()
        hero.setSpacing(20)

        logo = QLabel()
        png = ASSETS / "icon.png"
        if png.exists():
            pix = QPixmap(str(png)).scaled(
                72, 72,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
            logo.setPixmap(pix)
        hero.addWidget(logo, 0, Qt.AlignmentFlag.AlignTop)

        text_box = QVBoxLayout()
        text_box.setSpacing(6)
        eyebrow = QLabel("NEW BUNDLE")
        eyebrow.setObjectName("FieldLabel")
        title = QLabel("Assemble a court bundle")
        title.setObjectName("H1")
        sub = QLabel(
            "Indexer reads your main document, finds every annexure reference, "
            "matches them against a folder of source files, and produces a paginated bundle "
            "with an index, stamped annexures and continuous page numbers."
        )
        sub.setObjectName("Sub")
        sub.setWordWrap(True)
        text_box.addWidget(eyebrow)
        text_box.addWidget(title)
        text_box.addSpacing(2)
        text_box.addWidget(sub)
        hero.addLayout(text_box, 1)
        outer.addLayout(hero)

        # ── Form card ─────────────────────────────────────────
        card = Card()
        form = QVBoxLayout(card)
        form.setContentsMargins(32, 30, 32, 30)
        form.setSpacing(20)

        self.main_input = self._row(form, "Main document",
                                    "Choose a PDF or DOCX…", self._pick_main)
        self.pool_input = self._row(form, "Candidate folder",
                                    "Folder of annexure files…", self._pick_pool)
        self.out_input = self._row(form, "Output folder",
                                   "Where to save the bundle…", self._pick_out)
        outer.addWidget(card)

        # ── Footer / CTA ─────────────────────────────────────
        bottom = QHBoxLayout()
        hint = QLabel("All processing happens locally on your machine.")
        hint.setObjectName("Sub")
        bottom.addWidget(hint)
        bottom.addStretch(1)
        self.next_btn = QPushButton("Scan main document  →")
        self.next_btn.setObjectName("Primary")
        self.next_btn.setEnabled(False)
        self.next_btn.setMinimumHeight(42)
        self.next_btn.clicked.connect(self._emit_proceed)
        bottom.addWidget(self.next_btn)
        outer.addLayout(bottom)
        outer.addStretch(1)

        for inp in (self.main_input, self.pool_input, self.out_input):
            inp.textChanged.connect(self._refresh)

    def _row(self, layout, label, placeholder, on_browse):
        lbl = QLabel(label)
        lbl.setObjectName("FieldLabel")
        inp = QLineEdit()
        inp.setPlaceholderText(placeholder)
        inp.setMinimumHeight(40)
        btn = QPushButton("Browse")
        btn.setMinimumHeight(40)
        btn.clicked.connect(on_browse)
        h = QHBoxLayout()
        h.setSpacing(10)
        h.addWidget(inp, 1)
        h.addWidget(btn)
        layout.addWidget(lbl)
        layout.addLayout(h)
        return inp

    def _pick_main(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Select main document", "",
            "Documents (*.pdf *.docx *.doc)",
        )
        if path:
            self.main_input.setText(path)
            if not self.out_input.text():
                self.out_input.setText(str(Path(path).with_suffix("").parent / "Bundle"))

    def _pick_pool(self):
        path = QFileDialog.getExistingDirectory(self, "Select candidate folder")
        if path:
            self.pool_input.setText(path)

    def _pick_out(self):
        path = QFileDialog.getExistingDirectory(self, "Select output folder")
        if path:
            self.out_input.setText(path)

    def _refresh(self):
        ok = (
            Path(self.main_input.text()).is_file()
            and Path(self.pool_input.text()).is_dir()
            and self.out_input.text().strip() != ""
        )
        self.next_btn.setEnabled(ok)

    def _emit_proceed(self):
        self.proceed.emit(
            Path(self.main_input.text()),
            Path(self.pool_input.text()),
            Path(self.out_input.text()),
        )
