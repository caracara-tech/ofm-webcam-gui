"""Camera device/backend/resolution selection panel."""

from __future__ import annotations

from PyQt5.QtCore import pyqtSignal
from PyQt5.QtWidgets import QComboBox, QGridLayout, QGroupBox, QLabel, QPushButton, QSpinBox

from core.config import BACKENDS, RESOLUTIONS, default_backend_index


class CameraPanel(QGroupBox):
    """Lets the user pick a device index, backend, and resolution, and
    start/stop the stream. Emits signals; owns no camera I/O itself."""

    start_stream_requested = pyqtSignal()
    stop_stream_requested = pyqtSignal()
    detect_names_requested = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__("Camera", parent)
        layout = QGridLayout(self)

        layout.addWidget(QLabel("Device index:"), 0, 0)
        self.device_spin = QSpinBox()
        self.device_spin.setRange(0, 9)
        self.device_spin.setValue(0)
        layout.addWidget(self.device_spin, 0, 1)

        self.detect_names_btn = QPushButton("Detect Camera Names (Windows)")
        self.detect_names_btn.clicked.connect(self.detect_names_requested.emit)
        layout.addWidget(self.detect_names_btn, 1, 0, 1, 2)

        layout.addWidget(QLabel("Backend:"), 2, 0)
        self.backend_combo = QComboBox()
        for backend in BACKENDS:
            self.backend_combo.addItem(backend.label)
        self.backend_combo.setCurrentIndex(default_backend_index())
        layout.addWidget(self.backend_combo, 2, 1)

        layout.addWidget(QLabel("Resolution:"), 3, 0)
        self.resolution_combo = QComboBox()
        for res in RESOLUTIONS:
            self.resolution_combo.addItem(res.label)
        layout.addWidget(self.resolution_combo, 3, 1)

        self.start_btn = QPushButton("Start Stream")
        self.start_btn.clicked.connect(self._on_start_clicked)
        layout.addWidget(self.start_btn, 4, 0, 1, 2)

        self._streaming = False

    def _on_start_clicked(self) -> None:
        if self._streaming:
            self.stop_stream_requested.emit()
        else:
            self.start_stream_requested.emit()

    def set_streaming(self, streaming: bool) -> None:
        self._streaming = streaming
        self.start_btn.setText("Stop Stream" if streaming else "Start Stream")

    @property
    def device_index(self) -> int:
        return self.device_spin.value()

    @property
    def resolution(self):
        return RESOLUTIONS[self.resolution_combo.currentIndex()]

    @property
    def backend(self):
        return BACKENDS[self.backend_combo.currentIndex()]
