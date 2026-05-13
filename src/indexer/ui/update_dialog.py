"""Update-available modal dialog with background download + install."""
from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QPushButton,
    QTextBrowser,
    QVBoxLayout,
)

from ..updater import UpdateInfo, download_installer, launch_installer_and_exit


ASSETS = Path(__file__).resolve().parent.parent / "assets"


class _DownloadWorker(QThread):
    progress = Signal(int, int)
    finished_ok = Signal(str)        # path to downloaded installer
    failed = Signal(str)

    def __init__(self, info: UpdateInfo):
        super().__init__()
        self.info = info

    def run(self) -> None:
        try:
            path = download_installer(
                self.info,
                progress=lambda done, total: self.progress.emit(done, total),
            )
            self.finished_ok.emit(str(path))
        except Exception as e:
            self.failed.emit(str(e))


class UpdateDialog(QDialog):
    def __init__(self, info: UpdateInfo, parent=None):
        super().__init__(parent)
        self.info = info
        self._worker: _DownloadWorker | None = None
        self._installer_path: Path | None = None

        self.setWindowTitle("Indexer — Update available")
        self.setModal(True)
        self.setMinimumSize(560, 520)
        self.setObjectName("UpdateDialog")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setStyleSheet("QDialog#UpdateDialog { background:#F4F5F9; }")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(32, 28, 32, 24)
        layout.setSpacing(16)

        # Header
        header = QHBoxLayout()
        header.setSpacing(14)
        logo = QLabel()
        png = ASSETS / "icon.png"
        if png.exists():
            logo.setPixmap(QPixmap(str(png)).scaled(
                56, 56,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            ))
        header.addWidget(logo)

        title_box = QVBoxLayout()
        title_box.setSpacing(2)
        eyebrow = QLabel("UPDATE AVAILABLE")
        eyebrow.setObjectName("FieldLabel")
        title = QLabel(f"Indexer {info.latest_version} is ready")
        title.setObjectName("H1")
        sub = QLabel(f"You're currently running v{info.current_version}.")
        sub.setObjectName("Sub")
        title_box.addWidget(eyebrow)
        title_box.addWidget(title)
        title_box.addWidget(sub)
        header.addLayout(title_box, 1)
        layout.addLayout(header)

        # Release notes
        notes = QTextBrowser()
        notes.setOpenExternalLinks(True)
        notes_md = info.release_notes.strip() or "_No release notes provided._"
        notes.setMarkdown(notes_md)
        notes.setStyleSheet(
            "background:#FFFFFF; border:1px solid #E5E7EB; border-radius:10px;"
            "padding:14px; color:#1E293B; font-size:13px;"
        )
        layout.addWidget(notes, 1)

        # Progress bar (hidden until download starts)
        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        self.progress.setVisible(False)
        layout.addWidget(self.progress)

        self.status = QLabel("")
        self.status.setObjectName("Sub")
        self.status.setVisible(False)
        layout.addWidget(self.status)

        # Buttons
        row = QHBoxLayout()
        self.later_btn = QPushButton("Remind me later")
        self.later_btn.clicked.connect(self.reject)
        row.addWidget(self.later_btn)
        row.addStretch(1)
        self.install_btn = QPushButton("Install now")
        self.install_btn.setObjectName("Primary")
        self.install_btn.setMinimumHeight(40)
        self.install_btn.clicked.connect(self._start_download)
        row.addWidget(self.install_btn)
        layout.addLayout(row)

    def _start_download(self) -> None:
        self.install_btn.setEnabled(False)
        self.later_btn.setEnabled(False)
        self.progress.setVisible(True)
        self.status.setVisible(True)
        self.status.setText("Downloading update…")

        self._worker = _DownloadWorker(self.info)
        self._worker.progress.connect(self._on_progress)
        self._worker.finished_ok.connect(self._on_downloaded)
        self._worker.failed.connect(self._on_failed)
        self._worker.start()

    def _on_progress(self, done: int, total: int) -> None:
        if total <= 0:
            return
        pct = int(done * 100 / total)
        self.progress.setValue(pct)
        mb_done = done / (1024 * 1024)
        mb_total = total / (1024 * 1024)
        self.status.setText(f"Downloading… {mb_done:.1f} / {mb_total:.1f} MB")

    def _on_downloaded(self, path: str) -> None:
        self._installer_path = Path(path)
        self.status.setText("Download complete. Launching installer…")
        launch_installer_and_exit(self._installer_path)

    def _on_failed(self, msg: str) -> None:
        self.status.setText(f"Update failed: {msg}")
        self.install_btn.setEnabled(True)
        self.later_btn.setEnabled(True)
