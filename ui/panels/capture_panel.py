"""Snapshot and video recording controls."""

from __future__ import annotations

from pathlib import Path

from PyQt5.QtCore import pyqtSignal
from PyQt5.QtWidgets import QCheckBox, QGridLayout, QGroupBox, QLabel, QLineEdit, QPushButton

from core.i18n import _


class CapturePanel(QGroupBox):
    """Output folder (path, choose, open), snapshot and recording buttons, and
    the timestamp overlay toggle that applies to what they save."""

    browse_requested = pyqtSignal()
    open_folder_requested = pyqtSignal()
    snapshot_requested = pyqtSignal()
    recording_toggled = pyqtSignal()

    def __init__(self, output_dir: Path, parent=None):
        super().__init__(_("Snapshots & Recording"), parent)
        layout = QGridLayout(self)

        layout.addWidget(QLabel(_("Output folder:")), 0, 0, 1, 3)
        self.output_edit = QLineEdit(str(output_dir))
        self.output_edit.setReadOnly(True)
        layout.addWidget(self.output_edit, 1, 0)

        # "Browse" picks a folder (the dialog only lists folders); "Open folder"
        # shows the folder in the file manager so the saved files are visible.
        browse_btn = QPushButton(_("Browse"))
        browse_btn.clicked.connect(self.browse_requested.emit)
        layout.addWidget(browse_btn, 1, 1)
        self.open_folder_btn = QPushButton(_("Open folder"))
        self.open_folder_btn.setToolTip(_("Open this folder in the file manager"))
        self.open_folder_btn.clicked.connect(self.open_folder_requested.emit)
        layout.addWidget(self.open_folder_btn, 1, 2)

        self.snapshot_btn = QPushButton(_("Save Snapshot (PNG)"))
        self.snapshot_btn.clicked.connect(self.snapshot_requested.emit)
        layout.addWidget(self.snapshot_btn, 2, 0, 1, 3)

        self.record_btn = QPushButton(_("Start Recording (.mp4)"))
        self.record_btn.clicked.connect(self.recording_toggled.emit)
        layout.addWidget(self.record_btn, 3, 0, 1, 3)

        self.timestamp_chk = QCheckBox(_("Burn timestamp into frame"))
        self.timestamp_chk.setChecked(True)
        layout.addWidget(self.timestamp_chk, 4, 0, 1, 3)

    def set_output_dir_text(self, path: Path) -> None:
        self.output_edit.setText(str(path))

    def set_recording(self, recording: bool) -> None:
        self.record_btn.setText(_("Stop Recording") if recording else _("Start Recording (.mp4)"))

    @property
    def burn_timestamp(self) -> bool:
        return self.timestamp_chk.isChecked()
