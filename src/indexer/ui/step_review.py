"""Step 2: review proposed matches; reassign or skip per annexure."""
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
    QVBoxLayout,
    QWidget,
)

from ..matcher import MatchResult
from .widgets import Card, ConfidencePill


class ReviewStep(QWidget):
    proceed = Signal(list)   # adjusted match results (with .ranked reordered)
    back = Signal()

    SKIP_VALUE = "__skip__"

    def __init__(self, parent=None):
        super().__init__(parent)
        self._matches: list[MatchResult] = []
        self._pool: list[Path] = []
        self._selection: dict[int, str] = {}   # index -> path or SKIP

        outer = QVBoxLayout(self)
        outer.setContentsMargins(40, 40, 40, 40)
        outer.setSpacing(16)

        header = QLabel("Review matches")
        header.setObjectName("H1")
        sub = QLabel(
            "Indexer suggests the best candidate for each annexure. "
            "Override any that look wrong, or mark as 'skip' if no candidate is right."
        )
        sub.setObjectName("Sub")
        sub.setWordWrap(True)
        outer.addWidget(header)
        outer.addWidget(sub)

        card = Card()
        cl = QVBoxLayout(card)
        cl.setContentsMargins(0, 0, 0, 0)
        self.list = QListWidget()
        self.list.setObjectName("ReviewList")
        self.list.setUniformItemSizes(False)
        cl.addWidget(self.list)
        outer.addWidget(card, 1)

        row = QHBoxLayout()
        back_btn = QPushButton("← Back")
        back_btn.clicked.connect(self.back.emit)
        row.addWidget(back_btn)
        row.addStretch(1)
        self.next_btn = QPushButton("Build bundle  →")
        self.next_btn.setObjectName("Primary")
        self.next_btn.clicked.connect(self._emit_proceed)
        row.addWidget(self.next_btn)
        outer.addLayout(row)

    def load(self, matches: list[MatchResult], pool: list[Path]) -> None:
        self._matches = matches
        self._pool = pool
        self._selection = {}
        self.list.clear()
        for i, mr in enumerate(matches):
            item = QListWidgetItem(self.list)
            widget = self._build_row(i, mr, pool)
            item.setSizeHint(widget.sizeHint())
            self.list.addItem(item)
            self.list.setItemWidget(item, widget)
            if mr.best:
                self._selection[i] = str(mr.best.path)
            else:
                self._selection[i] = self.SKIP_VALUE

    def _build_row(self, idx: int, mr: MatchResult, pool: list[Path]) -> QWidget:
        ref = mr.reference
        wrap = QWidget()
        wrap.setObjectName("ReviewRow")
        h = QHBoxLayout(wrap)
        h.setContentsMargins(18, 14, 18, 14)
        h.setSpacing(16)

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
        left_w.setMinimumWidth(220)
        left_w.setMaximumWidth(260)
        h.addWidget(left_w)

        mid = QVBoxLayout()
        combo = QComboBox()
        for cs in mr.ranked:
            combo.addItem(f"{cs.path.name}   —   score {cs.score:.0f}", str(cs.path))
        # Add the rest of the pool as fallback options
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

        pill = ConfidencePill(
            mr.confidence,
            mr.best.score if mr.best else None,
        )
        h.addWidget(pill, 0, Qt.AlignmentFlag.AlignTop)
        return wrap

    def _on_change(self, idx: int, combo: QComboBox) -> None:
        self._selection[idx] = combo.currentData()

    def _emit_proceed(self) -> None:
        adjusted: list[MatchResult] = []
        for i, mr in enumerate(self._matches):
            chosen = self._selection.get(i, self.SKIP_VALUE)
            if chosen == self.SKIP_VALUE:
                mr_copy = MatchResult(reference=mr.reference, ranked=[])
            else:
                chosen_path = Path(chosen)
                # Find the CandidateScore for chosen_path, or fabricate one
                cs = next((c for c in mr.ranked if str(c.path) == chosen), None)
                if cs is None:
                    from ..matcher import CandidateScore
                    cs = CandidateScore(
                        path=chosen_path, score=100.0,
                        filename_score=100.0, content_score=0.0, label_hit=False,
                    )
                # Put chosen at the front
                rest = [c for c in mr.ranked if str(c.path) != chosen]
                mr_copy = MatchResult(reference=mr.reference, ranked=[cs] + rest)
            adjusted.append(mr_copy)
        self.proceed.emit(adjusted)
