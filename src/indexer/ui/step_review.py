"""Step 2: review proposed matches; reassign, remove, or skip per annexure."""
from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from ..matcher import MatchResult
from .preview import PdfPreview
from .widgets import Card, ConfidencePill


class ReviewStep(QWidget):
    proceed = Signal(list)
    back = Signal()

    SKIP_VALUE = "__skip__"

    def __init__(self, parent=None):
        super().__init__(parent)
        self._matches: list[MatchResult] = []
        self._pool: list[Path] = []
        self._removed: set[int] = set()
        self._selection: dict[int, str] = {}

        outer = QVBoxLayout(self)
        outer.setContentsMargins(40, 40, 40, 36)
        outer.setSpacing(16)

        header = QLabel("Review matches")
        header.setObjectName("H1")
        sub = QLabel(
            "Indexer suggests the best candidate for each annexure. "
            "Override any that look wrong, mark Skip when no candidate fits, "
            "or Remove the row entirely if the reference was a false positive. "
            "Click any row to preview the selected file."
        )
        sub.setObjectName("Sub")
        sub.setWordWrap(True)
        outer.addWidget(header)
        outer.addWidget(sub)

        # Splitter: list on left, preview on right
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setHandleWidth(12)
        splitter.setChildrenCollapsible(False)

        list_card = Card()
        list_layout = QVBoxLayout(list_card)
        list_layout.setContentsMargins(0, 0, 0, 0)
        self.list = QListWidget()
        self.list.setObjectName("ReviewList")
        self.list.setUniformItemSizes(False)
        self.list.currentItemChanged.connect(self._on_item_changed)
        list_layout.addWidget(self.list)
        splitter.addWidget(list_card)

        self.preview = PdfPreview()
        splitter.addWidget(self.preview)
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 2)
        splitter.setSizes([700, 380])

        outer.addWidget(splitter, 1)

        row = QHBoxLayout()
        back_btn = QPushButton("← Back")
        back_btn.clicked.connect(self.back.emit)
        row.addWidget(back_btn)
        row.addStretch(1)
        self.status = QLabel("")
        self.status.setObjectName("Sub")
        row.addWidget(self.status)
        row.addStretch(1)
        self.next_btn = QPushButton("Build bundle  →")
        self.next_btn.setObjectName("Primary")
        self.next_btn.setMinimumHeight(40)
        self.next_btn.clicked.connect(self._emit_proceed)
        row.addWidget(self.next_btn)
        outer.addLayout(row)

    # ── data ────────────────────────────────────────────────────
    def load(self, matches: list[MatchResult], pool: list[Path]) -> None:
        self._matches = matches
        self._pool = pool
        self._removed = set()
        self._selection = {}
        self.list.clear()
        for i, mr in enumerate(matches):
            self._add_row(i, mr, pool)
            self._selection[i] = str(mr.best.path) if mr.best else self.SKIP_VALUE
        if self.list.count():
            self.list.setCurrentRow(0)
        self._update_status()

    def _add_row(self, idx: int, mr: MatchResult, pool: list[Path]) -> None:
        item = QListWidgetItem(self.list)
        widget = self._build_row(idx, mr, pool)
        item.setSizeHint(widget.sizeHint())
        item.setData(Qt.ItemDataRole.UserRole, idx)
        self.list.addItem(item)
        self.list.setItemWidget(item, widget)

    def _build_row(self, idx: int, mr: MatchResult, pool: list[Path]) -> QWidget:
        ref = mr.reference
        wrap = QWidget()
        wrap.setObjectName("ReviewRow")
        h = QHBoxLayout(wrap)
        h.setContentsMargins(18, 14, 18, 14)
        h.setSpacing(14)

        # Left: label + title
        left = QVBoxLayout()
        label = QLabel(f"Annexure {ref.label}")
        label.setObjectName("RefLabel")
        title = QLabel(ref.title or "(no title found)")
        title.setObjectName("RefTitle")
        title.setWordWrap(True)
        left.addWidget(label)
        left.addWidget(title)
        left.addStretch(1)
        left_w = QWidget()
        left_w.setLayout(left)
        left_w.setMinimumWidth(180)
        left_w.setMaximumWidth(220)
        h.addWidget(left_w)

        # Middle: selector
        mid = QVBoxLayout()
        combo = QComboBox()
        for cs in mr.ranked:
            combo.addItem(f"{cs.path.name}   —   score {cs.score:.0f}", str(cs.path))
        ranked_paths = {str(c.path) for c in mr.ranked}
        for p in pool:
            if str(p) not in ranked_paths:
                combo.addItem(p.name, str(p))
        combo.addItem("— Skip this annexure —", self.SKIP_VALUE)
        combo.currentIndexChanged.connect(
            lambda _i, ix=idx, c=combo: self._on_change(ix, c)
        )
        mid.addWidget(combo)
        if not mr.ranked:
            warn = QLabel("No automatic match. Pick manually.")
            warn.setObjectName("Warn")
            mid.addWidget(warn)
        mid.addStretch(1)
        mid_w = QWidget()
        mid_w.setLayout(mid)
        h.addWidget(mid_w, 1)

        # Right: confidence + remove
        pill = ConfidencePill(mr.confidence, mr.best.score if mr.best else None)
        h.addWidget(pill, 0, Qt.AlignmentFlag.AlignTop)

        remove_btn = QPushButton("Remove")
        remove_btn.setToolTip("Remove this reference entirely — useful if it's a false positive.")
        remove_btn.setFixedHeight(28)
        remove_btn.clicked.connect(lambda _checked=False, ix=idx: self._on_remove(ix))
        h.addWidget(remove_btn, 0, Qt.AlignmentFlag.AlignTop)

        return wrap

    # ── interactions ────────────────────────────────────────────
    def _on_change(self, idx: int, combo: QComboBox) -> None:
        self._selection[idx] = combo.currentData()
        # Update preview if this row is currently selected
        current = self.list.currentItem()
        if current is not None and current.data(Qt.ItemDataRole.UserRole) == idx:
            self._update_preview_for(idx)

    def _on_item_changed(self, current: QListWidgetItem | None,
                         _previous: QListWidgetItem | None) -> None:
        if current is None:
            self.preview.clear()
            return
        idx = current.data(Qt.ItemDataRole.UserRole)
        self._update_preview_for(idx)

    def _update_preview_for(self, idx: int) -> None:
        path_str = self._selection.get(idx)
        if not path_str or path_str == self.SKIP_VALUE:
            self.preview.clear()
            return
        self.preview.show_file(Path(path_str))

    def _on_remove(self, idx: int) -> None:
        self._removed.add(idx)
        # Find and hide the row
        for i in range(self.list.count()):
            item = self.list.item(i)
            if item.data(Qt.ItemDataRole.UserRole) == idx:
                item.setHidden(True)
                break
        self._update_status()

    def _update_status(self) -> None:
        active = len(self._matches) - len(self._removed)
        self.status.setText(f"{active} of {len(self._matches)} references active")

    # ── output ──────────────────────────────────────────────────
    def _emit_proceed(self) -> None:
        adjusted: list[MatchResult] = []
        for i, mr in enumerate(self._matches):
            if i in self._removed:
                continue
            chosen = self._selection.get(i, self.SKIP_VALUE)
            if chosen == self.SKIP_VALUE:
                adjusted.append(MatchResult(reference=mr.reference, ranked=[]))
                continue
            cs = next((c for c in mr.ranked if str(c.path) == chosen), None)
            if cs is None:
                from ..matcher import CandidateScore
                cs = CandidateScore(
                    path=Path(chosen), score=100.0,
                    filename_score=100.0, content_score=0.0,
                    date_overlap=0, noun_overlap=0, label_hit=False,
                )
            rest = [c for c in mr.ranked if str(c.path) != chosen]
            adjusted.append(MatchResult(reference=mr.reference, ranked=[cs] + rest))
        self.proceed.emit(adjusted)
