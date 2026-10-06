"""Snapshot and video recording controls."""

from __future__ import annotations

from pathlib import Path

from PyQt5.QtCore import pyqtSignal
from PyQt5.QtWidgets import QCheckBox, QGridLayout, QGroupBox, QLabel, QLineEdit, QPushButton


class CapturePanel(QGroupBox):
    """Output folder, timestamp overlay toggle, snapshot and recording buttons."""

    browse_requested = pyqtSignal()
    snapshot_requested = pyqtSignal()
    recording_toggled = pyqtSignal()

    def __init__(self, output_dir: Path, parent=None):
        super().__init__("Snapshots & Recording", parent)
        layout = QGridLayout(self)

        layout.addWidget(QLabel("Output folder:"), 0, 0, 1, 2)
        self.output_edit = QLineEdit(str(output_dir))
        self.output_edit.setReadOnly(True)
        layout.addWidget(self.output_edit, 1, 0)
        browse_btn = QPushButton("Browse")
        browse_btn.clicked.connect(self.browse_requested.emit)
        layout.addWidget(browse_btn, 1, 1)

        self.timestamp_chk = QCheckBox("Burn timestamp into frame")
        self.timestamp_chk.setChecked(True)
        layout.addWidget(self.timestamp_chk, 2, 0, 1, 2)

        self.snapshot_btn = QPushButton("Save Snapshot (PNG)")
        self.snapshot_btn.clicked.connect(self.snapshot_requested.emit)
        layout.addWidget(self.snapshot_btn, 3, 0, 1, 2)

        self.record_btn = QPushButton("Start Recording (.mp4)")
        self.record_btn.clicked.connect(self.recording_toggled.emit)
        layout.addWidget(self.record_btn, 4, 0, 1, 2)

    def set_output_dir_text(self, path: Path) -> None:
        self.output_edit.setText(str(path))

    def set_recording(self, recording: bool) -> None:
        self.record_btn.setText("Stop Recording" if recording else "Start Recording (.mp4)")

    @property
    def burn_timestamp(self) -> bool:
        return self.timestamp_chk.isChecked()
