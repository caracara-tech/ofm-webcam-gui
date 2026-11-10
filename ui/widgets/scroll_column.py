"""
The controls column (camera, capture, stage, display panels) is taller than a
720p screen. Put directly in the window's layout, its height becomes the
window's minimum height, so the window cannot be shrunk and the layout breaks
when content changes. Inside a ScrollColumn the column keeps its natural width,
takes whatever height the window gives it, and scrolls when that is not enough.

The width is *derived* from the content (and re-derived when fonts, style or
screen change) rather than frozen once with a pixel value, so moving the window
to a screen with a different DPI cannot leave the controls clipped or squeezed.
"""

from __future__ import annotations

from PyQt5.QtCore import QEvent, QObject, QSize, Qt, QTimer
from PyQt5.QtWidgets import QFrame, QScrollArea, QSizePolicy, QStyle, QWidget

MIN_COLUMN_WIDTH = 280  # never narrower than this, even for very short labels
MIN_COLUMN_HEIGHT = 160  # enough to show a bit of the column before it scrolls

_GEOMETRY_EVENTS = (QEvent.LayoutRequest, QEvent.FontChange, QEvent.StyleChange, QEvent.PolishRequest)


class ScrollColumn(QScrollArea):
    def __init__(self, content: QWidget, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setFrameShape(QFrame.NoFrame)
        self.setWidgetResizable(True)  # content follows our width; its height-for-width is honoured
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        # Width follows sizeHint() (Fixed); height is whatever the window gives.
        self.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Expanding)
        self.setWidget(content)
        # Content width can change after construction (language fixed, but fonts,
        # style and screen DPI are not): tell the window's layout when it does.
        content.installEventFilter(self)

    # ------------------------------------------------------------ geometry ---
    def _column_width(self) -> int:
        content = self.widget()
        content_width = max(MIN_COLUMN_WIDTH, content.minimumSizeHint().width()) if content else MIN_COLUMN_WIDTH
        # Always reserve the scroll bar's space: the column must not change width
        # (and shove the video) when the bar appears or disappears.
        bar = self.style().pixelMetric(QStyle.PM_ScrollBarExtent, None, self)
        return content_width + bar + 2 * self.frameWidth()

    def sizeHint(self) -> QSize:
        content = self.widget()
        height = content.sizeHint().height() if content else MIN_COLUMN_HEIGHT
        return QSize(self._column_width(), max(MIN_COLUMN_HEIGHT, height))

    def minimumSizeHint(self) -> QSize:
        return QSize(self._column_width(), MIN_COLUMN_HEIGHT)

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:  # noqa: N802 (Qt naming)
        if watched is self.widget() and event.type() in _GEOMETRY_EVENTS:
            self.updateGeometry()
        return super().eventFilter(watched, event)

    def changeEvent(self, event: QEvent) -> None:  # noqa: N802
        super().changeEvent(event)
        if event.type() in (QEvent.FontChange, QEvent.StyleChange):
            self.updateGeometry()

    # --------------------------------------------------------------- helpers --
    def refresh_geometry(self) -> None:
        """Re-derive the width from the content (e.g. after the window moved to a
        screen with another DPI, which Qt does not report to child widgets)."""
        self.updateGeometry()

    def reveal(self, widget: QWidget) -> None:
        """Scroll so `widget` is fully visible, once the layout has settled
        (call after something inside it grew, e.g. an expanded section)."""
        QTimer.singleShot(0, lambda: self.ensureWidgetVisible(widget, 0, 8))
