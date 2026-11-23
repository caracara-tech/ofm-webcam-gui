"""Snapshot and video recording controls."""

from __future__ import annotations

from pathlib import Path

from PyQt5.QtCore import pyqtSignal
from PyQt5.QtWidgets import QCheckBox, QGridLayout, QLabel, QLineEdit, QPushButton

from core.help_topics import HelpTopic
from core.i18n import _
from ui.widgets.help import HelpGroupBox, add_help, reserve_help_column, set_tip


_HELP_COLUMN = 3  # the controls use columns 0-2; this one is reserved for the "?" marks


class CapturePanel(HelpGroupBox):
    """Output folder (path, choose, open), snapshot and recording buttons, and
    the timestamp overlay toggle that applies to what they save."""

    browse_requested = pyqtSignal()
    open_folder_requested = pyqtSignal()
    snapshot_requested = pyqtSignal()
    recording_toggled = pyqtSignal()

    def __init__(self, output_dir: Path, parent=None):
        super().__init__(_("Snapshots & Recording").replace("&", "&&"), parent)  # "&&": a literal & in a title, not a mnemonic
        self.set_help(HelpTopic.CAPTURE_SECTION)
        layout = QGridLayout(self)
        reserve_help_column(layout, _HELP_COLUMN)

        folder_label = QLabel(_("Output folder:"))
        set_tip(folder_label, HelpTopic.CAPTURE_OUTPUT_FOLDER)
        layout.addWidget(folder_label, 0, 0, 1, 3)
        self.output_edit = QLineEdit(str(output_dir))
        self.output_edit.setReadOnly(True)
        set_tip(self.output_edit, HelpTopic.CAPTURE_OUTPUT_FOLDER)
        layout.addWidget(self.output_edit, 1, 0)

        # "Browse" picks a folder (the dialog only lists folders); "Open folder"
        # shows the folder in the file manager so the saved files are visible.
        browse_btn = QPushButton(_("Browse"))
        set_tip(browse_btn, HelpTopic.CAPTURE_BROWSE)
        browse_btn.clicked.connect(self.browse_requested.emit)
        layout.addWidget(browse_btn, 1, 1)
        self.open_folder_btn = QPushButton(_("Open folder"))
        set_tip(self.open_folder_btn, HelpTopic.CAPTURE_OPEN_FOLDER)
        self.open_folder_btn.clicked.connect(self.open_folder_requested.emit)
        layout.addWidget(self.open_folder_btn, 1, 2)

        self.snapshot_btn = QPushButton(_("Save Snapshot (PNG)"))
        set_tip(self.snapshot_btn, HelpTopic.CAPTURE_SNAPSHOT)
        self.snapshot_btn.clicked.connect(self.snapshot_requested.emit)
        layout.addWidget(self.snapshot_btn, 2, 0, 1, 3)

        self.record_btn = QPushButton(_("Start Recording (.mp4)"))
        self.record_btn.clicked.connect(self.recording_toggled.emit)
        layout.addWidget(self.record_btn, 3, 0, 1, 3)
        add_help(layout, 3, HelpTopic.CAPTURE_RECORDING, column=_HELP_COLUMN, tips=(self.record_btn,))

        self.timestamp_chk = QCheckBox(_("Burn timestamp into frame"))
        self.timestamp_chk.setChecked(True)
        layout.addWidget(self.timestamp_chk, 4, 0, 1, 3)
        add_help(layout, 4, HelpTopic.CAPTURE_TIMESTAMP, column=_HELP_COLUMN, tips=(self.timestamp_chk,))

    def set_output_dir_text(self, path: Path) -> None:
        self.output_edit.setText(str(path))

    def set_recording(self, recording: bool) -> None:
        self.record_btn.setText(_("Stop Recording") if recording else _("Start Recording (.mp4)"))

    @property
    def burn_timestamp(self) -> bool:
        return self.timestamp_chk.isChecked()
