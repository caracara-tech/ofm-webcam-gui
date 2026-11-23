"""Camera device/backend/resolution selection panel."""

from __future__ import annotations

from PyQt5.QtCore import pyqtSignal
from PyQt5.QtWidgets import QComboBox, QGridLayout, QLabel, QPushButton, QToolButton

from core.config import RESOLUTIONS, default_backend_position, platform_backends
from core.help_topics import HelpTopic
from core.i18n import _
from hardware.cameras import CameraDevice, list_cameras
from ui.widgets.help import HelpGroupBox, add_help, reserve_help_column, set_tip, tooltip_for

# Used only when the computer can't tell us which cameras exist, so the user
# can still try device indices by hand.
FALLBACK_DEVICE_COUNT = 10

_HELP_COLUMN = 3  # the controls use columns 0-2; this one is reserved for the "?" marks


class CameraPanel(HelpGroupBox):
    """Lets the user pick a camera by name, a backend and a resolution, and
    start/stop the stream. Emits signals; owns no camera I/O itself."""

    start_stream_requested = pyqtSignal()
    stop_stream_requested = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(_("Camera"), parent)
        self.set_help(HelpTopic.CAMERA_SECTION)
        layout = QGridLayout(self)
        reserve_help_column(layout, _HELP_COLUMN)

        device_label = QLabel(_("Device:"))
        set_tip(device_label, HelpTopic.CAMERA_DEVICE)
        layout.addWidget(device_label, 0, 0)
        self.device_combo = QComboBox()
        # Long camera names must not widen the whole controls column: show a
        # fixed-ish width and elide; the drop-down list still shows full names.
        self.device_combo.setSizeAdjustPolicy(QComboBox.AdjustToMinimumContentsLengthWithIcon)
        self.device_combo.setMinimumContentsLength(10)
        layout.addWidget(self.device_combo, 0, 1)

        self.refresh_btn = QToolButton()
        self.refresh_btn.setText("\u21bb")
        set_tip(self.refresh_btn, HelpTopic.CAMERA_REFRESH)
        self.refresh_btn.clicked.connect(self.refresh_devices)
        layout.addWidget(self.refresh_btn, 0, 2)

        backend_label = QLabel(_("Backend:"))
        layout.addWidget(backend_label, 1, 0)
        self.backend_combo = QComboBox()
        self._backends = platform_backends()
        for backend in self._backends:
            self.backend_combo.addItem(backend.label)
        self.backend_combo.setCurrentIndex(default_backend_position())
        layout.addWidget(self.backend_combo, 1, 1, 1, 2)
        add_help(layout, 1, HelpTopic.CAMERA_BACKEND, column=_HELP_COLUMN, tips=(backend_label, self.backend_combo))

        resolution_label = QLabel(_("Resolution:"))
        layout.addWidget(resolution_label, 2, 0)
        self.resolution_combo = QComboBox()
        for res in RESOLUTIONS:
            self.resolution_combo.addItem(res.label)
        layout.addWidget(self.resolution_combo, 2, 1, 1, 2)
        add_help(layout, 2, HelpTopic.CAMERA_RESOLUTION, column=_HELP_COLUMN, tips=(resolution_label, self.resolution_combo))

        self.start_btn = QPushButton(_("Start Stream"))
        self.start_btn.clicked.connect(self._on_start_clicked)
        set_tip(self.start_btn, HelpTopic.CAMERA_START)
        layout.addWidget(self.start_btn, 3, 0, 1, 3)

        # What `set_locked()` disables. Not the whole panel: the "?" buttons must keep working.
        self._lockable = (self.device_combo, self.refresh_btn, self.backend_combo, self.resolution_combo, self.start_btn)
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
        set_tip(self.device_combo, HelpTopic.CAMERA_DEVICE, extra=listing.note or "")
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

    def set_locked(self, locked: bool) -> None:
        """Disable the whole panel (device, backend, resolution, Start/Stop) while
        something needs the stream to keep running, e.g. an autofocus sweep."""
        for control in self._lockable:
            control.setEnabled(not locked)
        # The explanation goes on the Start/Stop button, the control the user is most likely to try.
        if locked:
            self.start_btn.setToolTip(tooltip_for(HelpTopic.LOCKED_DURING_AUTOFOCUS))
        else:
            set_tip(self.start_btn, HelpTopic.CAMERA_START)

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
