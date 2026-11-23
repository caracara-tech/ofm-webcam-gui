"""
Contextual help for the controls: one look and one behaviour everywhere.

* `set_tip(widget, topic)` - the control's tooltip, from the help registry
  (`core/help_topics.py`). Every control gets one this way.
* `add_help(layout, row, topic, column=...)` - a small "?" in the *help column*
  of a grid layout. Hovering it shows the full explanation as a tooltip; that is
  all it does (no click, no popup).
* `reserve_help_column(layout, column)` - every section keeps one narrow column at
  its right edge for the "?" marks, rows with or without one, so they line up in
  a single column and controls end at the same place in every row.
* `HelpGroupBox` - a group box with a "?" at the right end of its title row,
  in that same column.

The "?" is the plain text character in a circle, in the normal text colour.
Texts live in `core/help_topics.py`; nothing here knows what any of them says.
"""

from __future__ import annotations

import html
from typing import Iterable, Optional

from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFontMetrics, QPainter, QPalette, QPen
from PyQt5.QtWidgets import QGridLayout, QGroupBox, QToolTip, QWidget

from core.help_topics import HelpEntry, HelpTopic, help_entry
from core.i18n import _

TOOLTIP_WIDTH_CHARS = 42  # tooltips wrap at about this many characters


def _width_px(widget_font, chars: int) -> int:
    return QFontMetrics(widget_font).averageCharWidth() * chars


def tooltip_html(*paragraphs: str, title: str = "") -> str:
    """Rich text for a tooltip: plain text would not wrap and long help would
    stretch across the whole screen."""
    parts = []
    if title:
        parts.append(f"<b>{html.escape(title)}</b>")
    for text in paragraphs:
        parts.extend(html.escape(line) for line in text.split("\n") if line)
    body = "<br><br>".join(parts)
    width = _width_px(QToolTip.font(), TOOLTIP_WIDTH_CHARS)
    return f'<table width="{width}"><tr><td>{body}</td></tr></table>'


def tooltip_for(topic: HelpTopic, extra: str = "") -> str:
    """The standard tooltip of a control: the topic's summary (plus `extra`, for
    text only known at run time, e.g. a note about the camera list)."""
    return tooltip_html(help_entry(topic).summary, extra)


def set_tip(widget: QWidget, topic: HelpTopic, extra: str = "") -> None:
    widget.setToolTip(tooltip_for(topic, extra))


class HelpIndicator(QWidget):
    """A "?" in a circle. Hover: tooltip with the full text."""

    def __init__(self, topic: HelpTopic, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        entry = help_entry(topic)
        self.setToolTip(tooltip_html(entry.summary, entry.details, title=entry.title))
        self.setAccessibleName(_("Help: {title}").format(title=entry.title or entry.summary))
        side = self.fontMetrics().height()  # follows font size and DPI, no pixel constant
        self.setFixedSize(side, side)

    def paintEvent(self, _event) -> None:  # noqa: N802 (Qt naming)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setPen(QPen(self.palette().color(QPalette.WindowText), 1.0))
        painter.drawEllipse(self.rect().adjusted(1, 1, -1, -1))
        font = painter.font()
        font.setPointSizeF(font.pointSizeF() * 0.85)
        painter.setFont(font)
        painter.drawText(self.rect(), Qt.AlignCenter, "?")


def help_slot_width(widget: QWidget) -> int:
    """Width of the help column: that of one "?" in `widget`'s font."""
    return widget.fontMetrics().height()


def reserve_help_column(layout: QGridLayout, column: int) -> None:
    """Keep `column` of `layout` at the width of a "?" even where a row has none."""
    parent = layout.parentWidget()
    layout.setColumnMinimumWidth(column, help_slot_width(parent) if parent is not None else 0)


def add_help(
    layout: QGridLayout, row: int, topic: HelpTopic, *, column: int, tips: Iterable[QWidget] = (),
) -> None:
    """Put the "?" for `topic` in the help `column` of `row`. The widgets in
    `tips` (the control and its label) also get the topic's summary as tooltip.
    Controls never span into the help column, so the "?" marks of all rows line up."""
    layout.addWidget(HelpIndicator(topic), row, column, Qt.AlignVCenter | Qt.AlignRight)
    for widget in tips:
        set_tip(widget, topic)


class HelpGroupBox(QGroupBox):
    """A group box that can show a "?" at the right end of its title row, above
    the help column of its content. The "?" floats over the frame (no layout
    row), so sections stay as compact as they were."""

    def __init__(self, title: str, parent: Optional[QWidget] = None) -> None:
        super().__init__(title, parent)
        self._help_indicator: Optional[HelpIndicator] = None

    def set_help(self, topic: HelpTopic) -> None:
        self._help_indicator = HelpIndicator(topic, self)
        self._place_help_indicator()
        self._help_indicator.show()

    def _place_help_indicator(self) -> None:
        indicator = self._help_indicator
        if indicator is None:
            return
        # The content's right edge: the frame's own inset plus the layout margin.
        layout = self.layout()
        right_margin = self.contentsMargins().right() + (layout.contentsMargins().right() if layout is not None else 0)
        indicator.move(self.width() - right_margin - indicator.width(), 0)

    def resizeEvent(self, event) -> None:  # noqa: N802 (Qt naming)
        super().resizeEvent(event)
        self._place_help_indicator()
