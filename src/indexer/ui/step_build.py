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
        self.open_bundle_btn = QPushButton("Open bundle.pdf")
        self.open_bundle_btn.setEnabled(False)
        self.open_bundle_btn.clicked.connect(self._open_bundle)
        self.again_btn = QPushButton("Start another bundle")
        self.again_btn.setObjectName("Primary")
        self.again_btn.setMinimumHeight(40)
        self.again_btn.setEnabled(False)
        self.again_btn.clicked.connect(self.restart.emit)
        row.addWidget(self.open_btn)
        row.addWidget(self.open_bundle_btn)
        row.addStretch(1)
        row.addWidget(self.again_btn)
        outer.addLayout(row)
        outer.addStretch(1)

        self._bundle_path: Path | None = None

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
            f"<b>{n}</b> annexures copied, renamed and stamped.",
            f"Output folder: <code>{report['out_dir']}</code>",
        ]
        bundle_pdf = report.get("bundle_pdf")
        if bundle_pdf:
            lines.append(f"Merged bundle: <code>{bundle_pdf}</code>")
            self._bundle_path = Path(bundle_pdf)
            self.open_bundle_btn.setEnabled(True)
        else:
            self._bundle_path = None
            self.open_bundle_btn.setEnabled(False)
        if u:
            lines.append(f"<b>{u}</b> annexure(s) were skipped — see <i>report.json</i>.")
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
        if self._out_dir:
            self._launch(self._out_dir)

    def _open_bundle(self) -> None:
        if self._bundle_path and self._bundle_path.exists():
            self._launch(self._bundle_path)

    @staticmethod
    def _launch(path: Path) -> None:
        p = str(path)
        if sys.platform.startswith("win"):
            os.startfile(p)  # type: ignore[attr-defined]
        elif sys.platform == "darwin":
            subprocess.Popen(["open", p])
        else:
            subprocess.Popen(["xdg-open", p])
