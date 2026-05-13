"""Disclaimer dialog shown on every app launch."""
from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
)

ASSETS = Path(__file__).resolve().parent.parent / "assets"

DISCLAIMER_TEXT = """\
<p><b>Indexer is provided "as is", without warranty of any kind, express or implied.</b></p>

<p>This tool is an aid to bundle preparation. It uses pattern-matching and text similarity
to suggest which source files correspond to the annexures referenced in your main
document. <b>It does not understand your case</b> and it cannot guarantee that every
match is correct.</p>

<p>By using Indexer you accept that:</p>
<ul>
  <li>You use this software <b>at your own risk</b>.</li>
  <li>You are <b>solely responsible</b> for verifying that the bundle is accurate,
      complete, and properly paginated before filing or distribution.</li>
  <li>The author and contributors accept <b>no liability</b> for any loss, damage,
      adverse outcome, sanction or cost arising from your use of this software, however
      caused.</li>
  <li>You will <b>independently check every match, every page, and every annexure</b>
      against the underlying documents before relying on the bundle for any purpose.</li>
</ul>

<p>If you do not accept these terms, please close this window and do not use the
software.</p>
"""


class DisclaimerDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Indexer — Disclaimer")
        self.setModal(True)
        self.setMinimumSize(620, 560)
        self.setObjectName("DisclaimerDialog")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setStyleSheet("QDialog#DisclaimerDialog { background:#F4F5F9; }")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(32, 28, 32, 24)
        layout.setSpacing(18)

        # Header
        header = QHBoxLayout()
        header.setSpacing(14)
        logo = QLabel()
        png = ASSETS / "icon.png"
        if png.exists():
            pix = QPixmap(str(png)).scaled(
                56, 56,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
            logo.setPixmap(pix)
        header.addWidget(logo)

        title_box = QVBoxLayout()
        title_box.setSpacing(2)
        eyebrow = QLabel("IMPORTANT")
        eyebrow.setObjectName("FieldLabel")
        title = QLabel("Please read before continuing")
        title.setObjectName("H1")
        title_box.addWidget(eyebrow)
        title_box.addWidget(title)
        header.addLayout(title_box, 1)
        layout.addLayout(header)

        # Body
        body = QLabel(DISCLAIMER_TEXT)
        body.setObjectName("DisclaimerBody")
        body.setWordWrap(True)
        body.setTextFormat(Qt.TextFormat.RichText)
        body.setStyleSheet(
            "background:#FFFFFF; border:1px solid #E5E7EB; border-radius:10px;"
            "padding:18px; color:#1E293B; font-size:13px;"
        )
        body.setAlignment(Qt.AlignmentFlag.AlignTop)
        layout.addWidget(body, 1)

        # Acknowledgement
        self.check = QCheckBox(
            "I have read and accept the disclaimer, and I will independently "
            "verify my bundle before relying on it."
        )
        self.check.setStyleSheet(
            "QCheckBox { color:#0F172A; font-size:12px; font-weight:600; spacing:10px; }"
            "QCheckBox::indicator { width:18px; height:18px; }"
        )
        self.check.stateChanged.connect(lambda _s: self._on_check())
        layout.addWidget(self.check)

        # Buttons
        row = QHBoxLayout()
        cancel = QPushButton("Quit")
        cancel.clicked.connect(self.reject)
        self.continue_btn = QPushButton("Continue to Indexer")
        self.continue_btn.setObjectName("Primary")
        self.continue_btn.setEnabled(False)
        self.continue_btn.setMinimumHeight(40)
        self.continue_btn.clicked.connect(self.accept)
        row.addWidget(cancel)
        row.addStretch(1)
        row.addWidget(self.continue_btn)
        layout.addLayout(row)

    def _on_check(self) -> None:
        self.continue_btn.setEnabled(self.check.isChecked())
