"""Compact session-log controls for the status bar: save to file, view."""

from __future__ import annotations

from PyQt5.QtCore import pyqtSignal
from PyQt5.QtWidgets import QCheckBox, QHBoxLayout, QPushButton, QWidget

from core.i18n import _


class LogBar(QWidget):
    """A checkbox and a button, small enough to live in the status bar (the
    controls column is already as tall as a screen). Emits `save_toggled(bool)`
    and `view_requested`; owns no logging itself: MainWindow reacts, then
    reports the real outcome back through `set_saving()`."""

    save_toggled = pyqtSignal(bool)
    view_requested = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self.save_check = QCheckBox(_("Save log to file"))
        self.save_check.setToolTip(
            _("Write everything logged in this session to a file, starting from the beginning of the session")
        )
        self.save_check.toggled.connect(self.save_toggled.emit)
        layout.addWidget(self.save_check)

        self.view_btn = QPushButton(_("View log..."))
        self.view_btn.setToolTip(_("Show the log of this session in a window"))
        self.view_btn.clicked.connect(self.view_requested.emit)
        layout.addWidget(self.view_btn)

    def set_saving(self, saving: bool) -> None:
        """Reflect the real state without re-emitting `save_toggled`."""
        self.save_check.blockSignals(True)
        self.save_check.setChecked(saving)
        self.save_check.blockSignals(False)
