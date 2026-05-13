"""Shared custom widgets."""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QFont
from PySide6.QtWidgets import (
    QFrame,
    QGraphicsDropShadowEffect,
    QHBoxLayout,
    QLabel,
    QVBoxLayout,
    QWidget,
)


class ConfidencePill(QLabel):
    COLORS = {
        "high": ("#0F5132", "#D1E7DD"),
        "medium": ("#664D03", "#FFF3CD"),
        "low": ("#842029", "#F8D7DA"),
        "none": ("#41464B", "#E2E3E5"),
    }

    def __init__(self, confidence: str, score: float | None = None, parent=None):
        super().__init__(parent)
        label = confidence.upper()
        if score is not None:
            label += f"  {score:.0f}"
        self.setText(label)
        fg, bg = self.COLORS.get(confidence, self.COLORS["none"])
        self.setStyleSheet(
            f"background:{bg}; color:{fg}; border-radius:11px;"
            f"padding:4px 12px; font-weight:700; font-size:11px;"
            f"letter-spacing:0.6px;"
        )
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setFixedHeight(26)
        self.setMaximumWidth(120)


class StepRow(QFrame):
    """A single row in the sidebar — number disc + label + accent bar."""

    def __init__(self, number: int, name: str, parent=None):
        super().__init__(parent)
        self.setObjectName("StepRow")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setProperty("active", False)
        self.setProperty("done", False)

        outer = QHBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        self.bar = QFrame()
        self.bar.setObjectName("StepBar")
        self.bar.setFixedWidth(4)
        outer.addWidget(self.bar)

        inner = QHBoxLayout()
        inner.setContentsMargins(20, 12, 18, 12)
        inner.setSpacing(14)

        self.num = QLabel(str(number))
        self.num.setObjectName("StepNumber")
        self.num.setFixedSize(30, 30)
        self.num.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.label = QLabel(name)
        self.label.setObjectName("StepLabel")

        inner.addWidget(self.num)
        inner.addWidget(self.label, 1)

        wrap = QWidget()
        wrap.setLayout(inner)
        outer.addWidget(wrap, 1)

    def set_state(self, active: bool, done: bool) -> None:
        for w in (self, self.num, self.label, self.bar):
            w.setProperty("active", active)
            w.setProperty("done", done)
            w.style().unpolish(w)
            w.style().polish(w)


class StepIndicator(QWidget):
    """Vertical step navigation on the left side."""

    def __init__(self, steps: list[str], parent=None):
        super().__init__(parent)
        self.setObjectName("StepIndicator")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 30, 0, 22)
        layout.setSpacing(0)

        # Brand block
        brand_box = QVBoxLayout()
        brand_box.setContentsMargins(24, 0, 24, 0)
        brand_box.setSpacing(2)

        brand = QLabel("INDEXER")
        brand.setObjectName("Brand")
        f = QFont("Segoe UI", 18)
        f.setWeight(QFont.Weight.Black)
        f.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, 4)
        brand.setFont(f)
        brand_box.addWidget(brand)

        accent = QFrame()
        accent.setObjectName("BrandAccent")
        accent.setFixedSize(36, 3)
        brand_box.addWidget(accent)

        tagline = QLabel("Legal Bundle Assembler")
        tagline.setObjectName("Tagline")
        brand_box.addSpacing(8)
        brand_box.addWidget(tagline)
        layout.addLayout(brand_box)

        layout.addSpacing(36)

        # Section heading
        section = QLabel("WORKFLOW")
        section.setObjectName("SectionHeading")
        section.setContentsMargins(24, 0, 24, 0)
        layout.addWidget(section)
        layout.addSpacing(8)

        self._rows: list[StepRow] = []
        for i, name in enumerate(steps, 1):
            row = StepRow(i, name)
            layout.addWidget(row)
            self._rows.append(row)

        layout.addStretch(1)

        footer_box = QVBoxLayout()
        footer_box.setContentsMargins(24, 0, 24, 0)
        footer_box.setSpacing(2)
        offline = QLabel("● Offline mode")
        offline.setObjectName("OfflineBadge")
        footer = QLabel("v0.1.0")
        footer.setObjectName("Footer")
        footer_box.addWidget(offline)
        footer_box.addWidget(footer)
        layout.addLayout(footer_box)

    def set_active(self, idx: int) -> None:
        for i, row in enumerate(self._rows):
            row.set_state(active=(i == idx), done=(i < idx))


class Card(QFrame):
    """Rounded white card with a soft drop shadow."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("Card")
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(28)
        shadow.setOffset(0, 6)
        shadow.setColor(QColor(15, 23, 42, 38))
        self.setGraphicsEffect(shadow)
