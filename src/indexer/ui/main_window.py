"""Top-level window orchestrating the three workflow steps."""
from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QThread
from PySide6.QtWidgets import (
    QHBoxLayout,
    QMainWindow,
    QMessageBox,
    QStackedWidget,
    QWidget,
)

from .step_build import BuildStep
from .step_review import ReviewStep
from .step_select import SelectStep
from .widgets import StepIndicator
from .workers import BuildWorker, MatchWorker, ScanWorker


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Indexer — Legal Bundle Assembler")
        self.resize(1100, 720)
        self.setMinimumSize(960, 600)

        root = QWidget()
        self.setCentralWidget(root)
        layout = QHBoxLayout(root)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.sidebar = StepIndicator(["Select files", "Review matches", "Build bundle"])
        self.sidebar.setFixedWidth(260)
        layout.addWidget(self.sidebar)

        self.stack = QStackedWidget()
        self.stack.setObjectName("Stack")
        layout.addWidget(self.stack, 1)

        self.select_step = SelectStep()
        self.review_step = ReviewStep()
        self.build_step = BuildStep()
        for w in (self.select_step, self.review_step, self.build_step):
            self.stack.addWidget(w)

        self.select_step.proceed.connect(self._on_select_proceed)
        self.review_step.back.connect(lambda: self._go(0))
        self.review_step.proceed.connect(self._on_review_proceed)
        self.build_step.restart.connect(self._restart)

        self._main_path: Path | None = None
        self._pool: list[Path] = []
        self._out_dir: Path | None = None
        self._refs = []
        self._thread: QThread | None = None
        self._worker = None

        self._go(0)

    # ── navigation ────────────────────────────────────────────────
    def _go(self, idx: int) -> None:
        self.stack.setCurrentIndex(idx)
        self.sidebar.set_active(idx)

    # ── step 1 → scan + match ────────────────────────────────────
    def _on_select_proceed(self, main_path: Path, pool_dir: Path, out_dir: Path) -> None:
        self._main_path = main_path
        self._out_dir = out_dir
        self._run_thread(
            ScanWorker(main_path, pool_dir),
            on_ok=self._on_scanned,
        )

    def _on_scanned(self, refs, pool) -> None:
        if not refs:
            QMessageBox.warning(
                self, "No references found",
                "Indexer did not find any annexure references in this document.",
            )
            return
        self._refs = refs
        self._pool = pool
        self._run_thread(
            MatchWorker(refs, pool),
            on_ok=self._on_matched,
        )

    def _on_matched(self, matches) -> None:
        self.review_step.load(matches, self._pool)
        self._go(1)

    # ── step 2 → build ───────────────────────────────────────────
    def _on_review_proceed(self, adjusted_matches) -> None:
        assert self._main_path and self._out_dir
        self._go(2)
        self.build_step.show_running(self._out_dir)
        self._run_thread(
            BuildWorker(adjusted_matches, self._main_path, self._out_dir, "low"),
            on_ok=self.build_step.show_success,
            on_fail=self.build_step.show_failure,
        )

    def _restart(self) -> None:
        self._go(0)

    # ── threading helper ─────────────────────────────────────────
    def _run_thread(self, worker, on_ok, on_fail=None) -> None:
        thread = QThread(self)
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        worker.finished.connect(on_ok)
        if on_fail:
            worker.failed.connect(on_fail)
        else:
            worker.failed.connect(self._show_error)
        worker.finished.connect(thread.quit)
        worker.failed.connect(thread.quit)
        thread.finished.connect(worker.deleteLater)
        thread.finished.connect(thread.deleteLater)
        self._thread = thread
        self._worker = worker
        thread.start()

    def _show_error(self, msg: str) -> None:
        QMessageBox.critical(self, "Error", msg)
