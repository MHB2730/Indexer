"""Step 3: build the bundle and show the result."""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from .widgets import Card


class BuildStep(QWidget):
    restart = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._out_dir: Path | None = None

        outer = QVBoxLayout(self)
        outer.setContentsMargins(40, 40, 40, 40)
        outer.setSpacing(20)

        self.title = QLabel("Building bundle…")
        self.title.setObjectName("H1")
        outer.addWidget(self.title)

        self.subtitle = QLabel("Copying annexures, renaming, building index and annotating main document.")
        self.subtitle.setObjectName("Sub")
        self.subtitle.setWordWrap(True)
        outer.addWidget(self.subtitle)

        card = Card()
        cl = QVBoxLayout(card)
        cl.setContentsMargins(28, 28, 28, 28)
        cl.setSpacing(16)

        self.progress = QProgressBar()
        self.progress.setRange(0, 0)
        cl.addWidget(self.progress)

        self.summary = QLabel("")
        self.summary.setObjectName("Summary")
        self.summary.setWordWrap(True)
        self.summary.setTextInteractionFlags(Qt.TextInteractionFlag.TextBrowserInteraction)
        cl.addWidget(self.summary)

        outer.addWidget(card)

        row = QHBoxLayout()
        self.open_btn = QPushButton("Open output folder")
        self.open_btn.setEnabled(False)
        self.open_btn.clicked.connect(self._open_folder)
        self.again_btn = QPushButton("Start another bundle")
        self.again_btn.setObjectName("Primary")
        self.again_btn.setEnabled(False)
        self.again_btn.clicked.connect(self.restart.emit)
        row.addWidget(self.open_btn)
        row.addStretch(1)
        row.addWidget(self.again_btn)
        outer.addLayout(row)
        outer.addStretch(1)

    def show_running(self, out_dir: Path) -> None:
        self._out_dir = out_dir
        self.title.setText("Building bundle…")
        self.progress.setRange(0, 0)
        self.summary.setText("")
        self.open_btn.setEnabled(False)
        self.again_btn.setEnabled(False)

    def show_success(self, report: dict) -> None:
        self.progress.setRange(0, 1)
        self.progress.setValue(1)
        n = len(report["entries"])
        u = len(report["unresolved"])
        self.title.setText("Bundle ready")
        lines = [
            f"<b>{n}</b> annexures copied, renamed, and indexed.",
        ]
        if u:
            lines.append(f"<b>{u}</b> annexure(s) were skipped — see <i>report.json</i>.")
        lines.append(f"Output folder: <code>{report['out_dir']}</code>")
        lines.append("")
        lines.append("Files written:")
        for e in report["entries"]:
            lines.append(f"&nbsp;&nbsp;{e['output_name']}")
        self.summary.setText("<br>".join(lines))
        self.open_btn.setEnabled(True)
        self.again_btn.setEnabled(True)

    def show_failure(self, msg: str) -> None:
        self.progress.setRange(0, 1)
        self.progress.setValue(0)
        self.title.setText("Build failed")
        self.summary.setText(f"<span style='color:#842029'>{msg}</span>")
        self.again_btn.setEnabled(True)

    def _open_folder(self) -> None:
        if not self._out_dir:
            return
        path = str(self._out_dir)
        if sys.platform.startswith("win"):
            os.startfile(path)  # type: ignore[attr-defined]
        elif sys.platform == "darwin":
            subprocess.Popen(["open", path])
        else:
            subprocess.Popen(["xdg-open", path])
