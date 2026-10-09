"""Camera device/backend/resolution selection panel."""

from __future__ import annotations

from PyQt5.QtCore import pyqtSignal
from PyQt5.QtWidgets import QComboBox, QGridLayout, QGroupBox, QLabel, QPushButton, QToolButton

from core.config import RESOLUTIONS, default_backend_position, platform_backends
from core.i18n import _
from hardware.cameras import CameraDevice, list_cameras

# Used only when the computer can't tell us which cameras exist, so the user
# can still try device indices by hand.
FALLBACK_DEVICE_COUNT = 10


class CameraPanel(QGroupBox):
    """Lets the user pick a camera by name, a backend and a resolution, and
    start/stop the stream. Emits signals; owns no camera I/O itself."""

    start_stream_requested = pyqtSignal()
    stop_stream_requested = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(_("Camera"), parent)
        layout = QGridLayout(self)

        layout.addWidget(QLabel(_("Device:")), 0, 0)
        self.device_combo = QComboBox()
        # Long camera names must not widen the whole controls column: show a
        # fixed-ish width and elide; the drop-down list still shows full names.
        self.device_combo.setSizeAdjustPolicy(QComboBox.AdjustToMinimumContentsLengthWithIcon)
        self.device_combo.setMinimumContentsLength(10)
        layout.addWidget(self.device_combo, 0, 1)

        self.refresh_btn = QToolButton()
        self.refresh_btn.setText("\u21bb")
        self.refresh_btn.setToolTip(_("Refresh camera list"))
        self.refresh_btn.clicked.connect(self.refresh_devices)
        layout.addWidget(self.refresh_btn, 0, 2)

        layout.addWidget(QLabel(_("Backend:")), 1, 0)
        self.backend_combo = QComboBox()
        self._backends = platform_backends()
        for backend in self._backends:
            self.backend_combo.addItem(backend.label)
        self.backend_combo.setCurrentIndex(default_backend_position())
        layout.addWidget(self.backend_combo, 1, 1, 1, 2)

        layout.addWidget(QLabel(_("Resolution:")), 2, 0)
        self.resolution_combo = QComboBox()
        for res in RESOLUTIONS:
            self.resolution_combo.addItem(res.label)
        layout.addWidget(self.resolution_combo, 2, 1, 1, 2)

        self.start_btn = QPushButton(_("Start Stream"))
        self.start_btn.clicked.connect(self._on_start_clicked)
        layout.addWidget(self.start_btn, 3, 0, 1, 3)

        self._streaming = False
        self.refresh_devices()

    # ------------------------------------------------------------ devices --
    def refresh_devices(self) -> None:
        """(Re)read the connected cameras into the dropdown, keeping the
        current selection if that camera is still there."""
        previous = self.device_combo.currentData()
        listing = list_cameras()
        devices = listing.devices or [
            CameraDevice(index, _("Camera {index}").format(index=index)) for index in range(FALLBACK_DEVICE_COUNT)
        ]

        names = [d.name for d in devices]
        self.device_combo.clear()
        for device in devices:
            # Two identical cameras would look the same: tell them apart by index.
            label = f"{device.name} ({device.index})" if names.count(device.name) > 1 else device.name
            self.device_combo.addItem(label, device.index)
        position = self.device_combo.findData(previous) if previous is not None else -1
        self.device_combo.setCurrentIndex(max(0, position))
        self.device_combo.setToolTip(listing.note or "")
        # The closed box elides long names; make the open list wide enough for them.
        view = self.device_combo.view()
        view.setMinimumWidth(view.sizeHintForColumn(0) + 30)

    def _on_start_clicked(self) -> None:
        if self._streaming:
            self.stop_stream_requested.emit()
        else:
            self.start_stream_requested.emit()

    def set_streaming(self, streaming: bool) -> None:
        self._streaming = streaming
        self.start_btn.setText(_("Stop Stream") if streaming else _("Start Stream"))

    @property
    def device_index(self) -> int:
        index = self.device_combo.currentData()
        return 0 if index is None else int(index)

    @property
    def resolution(self):
        return RESOLUTIONS[self.resolution_combo.currentIndex()]

    @property
    def backend(self):
        return self._backends[self.backend_combo.currentIndex()]
