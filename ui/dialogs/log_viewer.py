"""Live view of the session log, without leaving the program (scrolls with new lines unless you scrolled up).

Non-modal: it can stay open next to the main window and follows new messages as
they are logged. It reads from the in-memory `LogHistory` (core/logging_setup.py),
so it shows the whole session even if no log file is being written.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Callable, Optional

from PyQt5.QtCore import QObject, pyqtSignal
from PyQt5.QtGui import QFontDatabase
from PyQt5.QtWidgets import (
    QComboBox, QDialog, QFileDialog, QHBoxLayout, QLabel, QPlainTextEdit, QPushButton, QVBoxLayout, QWidget,
)

from core.i18n import _
from core.logging_setup import LogEntry, LogHistory

logger = logging.getLogger(__name__)


class _Relay(QObject):
    """Turns a log call from any thread into a signal the GUI thread receives.
    (Qt queues a signal emitted from another thread; widgets are never touched off-thread.)"""

    entry = pyqtSignal(object)


class LogViewerDialog(QDialog):
    open_folder_requested = pyqtSignal()

    def __init__(
        self,
        history: LogHistory,
        full_log: Optional[Callable[[], str]] = None,
        parent: Optional[QWidget] = None,
    ) -> None:
        """`full_log` returns the whole session as text (the history only keeps
        the last lines); "Save a copy..." uses it when given."""
        super().__init__(parent)
        self._history = history
        self._full_log = full_log
        self._min_level = logging.DEBUG
        self.setWindowTitle(_("Session log"))
        self.resize(900, 500)
        layout = QVBoxLayout(self)

        top = QHBoxLayout()
        top.addWidget(QLabel(_("Show:")))
        self.level_combo = QComboBox()
        # Each choice shows that level and everything more severe.
        for label, level in (
            (_("All messages"), logging.DEBUG),
            (_("Info and above"), logging.INFO),
            (_("Warnings and errors"), logging.WARNING),
            (_("Errors only"), logging.ERROR),
        ):
            self.level_combo.addItem(label, level)
        self.level_combo.currentIndexChanged.connect(self._on_filter_changed)
        top.addWidget(self.level_combo)
        top.addStretch()
        layout.addLayout(top)

        self.view = QPlainTextEdit()
        self.view.setReadOnly(True)
        self.view.setFont(QFontDatabase.systemFont(QFontDatabase.FixedFont))
        self.view.setLineWrapMode(QPlainTextEdit.NoWrap)
        layout.addWidget(self.view, stretch=1)

        bottom = QHBoxLayout()
        save_btn = QPushButton(_("Save a copy..."))
        save_btn.setToolTip(_("Write the whole session log (all levels) to a file of your choice"))
        save_btn.clicked.connect(self._save_copy)
        bottom.addWidget(save_btn)
        folder_btn = QPushButton(_("Open folder"))
        folder_btn.setToolTip(_("Open the log folder in the file manager"))
        folder_btn.clicked.connect(self.open_folder_requested.emit)
        bottom.addWidget(folder_btn)
        bottom.addStretch()
        close_btn = QPushButton(_("Close"))
        close_btn.clicked.connect(self.close)
        bottom.addWidget(close_btn)
        layout.addLayout(bottom)

        self._relay = _Relay()
        self._relay.entry.connect(self._on_entry)
        self._listener = self._relay.entry.emit
        self._render(history.subscribe(self._listener))

    # ------------------------------------------------------------ rendering --
    def _render(self, entries: list[LogEntry]) -> None:
        self.view.setPlainText("\n".join(e.text for e in entries if e.levelno >= self._min_level))
        self._scroll_to_end()

    def _on_entry(self, entry: LogEntry) -> None:
        if entry.levelno >= self._min_level:
            bar = self.view.verticalScrollBar()
            at_bottom = bar.value() >= bar.maximum() - 2  # keep reading older lines undisturbed
            self.view.appendPlainText(entry.text)
            if at_bottom:
                self._scroll_to_end()

    def _on_filter_changed(self, _index: int) -> None:
        self._min_level = int(self.level_combo.currentData())
        self._render(self._history.entries())

    def _scroll_to_end(self) -> None:
        bar = self.view.verticalScrollBar()
        bar.setValue(bar.maximum())

    # -------------------------------------------------------------- actions --
    def _save_copy(self) -> None:
        path, _filter = QFileDialog.getSaveFileName(
            self, _("Save a copy of the log"), str(Path.home() / "ofm-webcam-gui.log"), _("Log files (*.log *.txt)"),
        )
        if not path:
            return
        try:
            text = self._full_log() if self._full_log else "".join(e.text + "\n" for e in self._history.entries())
            Path(path).write_text(text, encoding="utf-8")
        except OSError as exc:
            logger.error("Could not save a copy of the log to %s: %s", path, exc)
        else:
            logger.info("Saved a copy of the session log to %s", path)

    # ------------------------------------------------------------ lifecycle --
    def closeEvent(self, event) -> None:
        self._history.unsubscribe(self._listener)
        super().closeEvent(event)

    def showEvent(self, event) -> None:
        # Reopening after a close: catch up on what was logged meanwhile and
        # start listening again (closeEvent stopped it).
        super().showEvent(event)
        if not self._history.is_subscribed(self._listener):
            self._render(self._history.subscribe(self._listener))
