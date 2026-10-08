"""Top-level QMainWindow. Wires panels + background threads together.

Deliberately thin: camera I/O lives in CameraThread, stage math lives in
core.stage_motion, stage backends live in hardware.stage. This class's job
is UI composition and event routing only.
"""

from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path
from typing import Optional

import cv2
import numpy as np
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QImage, QPixmap
from PyQt5.QtWidgets import (
    QFileDialog, QHBoxLayout, QLabel, QMainWindow, QMessageBox, QStatusBar, QVBoxLayout, QWidget,
)

from core.app_mode import AppMode
from core.config import DEFAULT_OUTPUT_DIR
from core.i18n import _
from core.overlays import draw_grid, draw_scale_bar
from core.version import __version__
from hardware.abstract import StageController
from hardware.camera_names import detect_camera_names
from .panels.camera_panel import CameraPanel
from .panels.capture_panel import CapturePanel
from .panels.display_panel import DisplayPanel
from .stage_module import StageModule
from .threads.camera_thread import ERR_LOST, ERR_NOT_DETECTED, CameraThread

logger = logging.getLogger(__name__)

APP_TITLE = "OFM Webcam Viewer v" + ".".join(__version__.split(".")[:2])  # e.g. "v0.1"
SNAPSHOT_FLASH_MS = 120
RECORDING_BLINK_INTERVAL_MS = 500


class MainWindow(QMainWindow):
    def __init__(self, mode: AppMode, stage: Optional[StageController] = None):
        super().__init__()
        if mode.has_stage != (stage is not None):
            raise ValueError(
                f"Mode {mode.value!r} {'needs' if mode.has_stage else 'does not take'} a stage controller"
            )
        self.mode = mode

        self._output_dir = DEFAULT_OUTPUT_DIR
        self._output_dir.mkdir(parents=True, exist_ok=True)

        self.camera_thread: Optional[CameraThread] = None
        self.video_writer: Optional[cv2.VideoWriter] = None
        self.last_frame: Optional[np.ndarray] = None
        self.frame_count = 0
        self.snapshot_count = 0
        self._recording_blink_on = False

        self.stage_module: Optional[StageModule] = None

        title_suffix = {
            AppMode.CAMERA_STAGE: _("Camera + Stage"),
            AppMode.CAMERA_ONLY: _("Camera"),
            AppMode.SIMULATION: _("SIMULATION"),
        }[mode]
        self.setWindowTitle(f"{APP_TITLE} - {title_suffix}")
        self.resize(900, 700)

        self._build_ui(stage)

        self.recording_blink_timer = QTimer(self)
        self.recording_blink_timer.timeout.connect(self._toggle_recording_blink)

    # ---------------------------------------------------------------- UI ---
    def _build_ui(self, stage: Optional[StageController]) -> None:
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QHBoxLayout(central)

        self.video_label = QLabel()
        self.video_label.setAlignment(Qt.AlignCenter)
        self.video_label.setStyleSheet("background-color: #111; color: #888;")
        self.video_label.setText(_("Camera stopped"))
        self.video_label.setWordWrap(True)
        self.video_label.setMinimumSize(640, 480)
        main_layout.addWidget(self.video_label, stretch=3)

        # Plain white overlay used for the snapshot "flash". Kept as a child
        # of video_label so it always sits exactly on top of the picture;
        # geometry is resynced whenever video_label's size changes.
        self.flash_overlay = QLabel(self.video_label)
        self.flash_overlay.setStyleSheet("background-color: white;")
        self.flash_overlay.hide()

        controls = QWidget()
        controls_layout = QVBoxLayout(controls)
        main_layout.addWidget(controls, stretch=0)

        self.camera_panel = CameraPanel()
        self.camera_panel.start_stream_requested.connect(self._start_stream)
        self.camera_panel.stop_stream_requested.connect(self._stop_stream)
        self.camera_panel.detect_names_requested.connect(self._detect_camera_names)
        controls_layout.addWidget(self.camera_panel)

        self.capture_panel = CapturePanel(self._output_dir)
        self.capture_panel.browse_requested.connect(self._choose_output_dir)
        self.capture_panel.snapshot_requested.connect(self._save_snapshot)
        self.capture_panel.recording_toggled.connect(self._toggle_recording)
        controls_layout.addWidget(self.capture_panel)

        if stage is not None:
            self.stage_module = StageModule(
                stage, self,
                get_frame=lambda: self.last_frame,
                get_frame_count=lambda: self.frame_count,
                is_streaming=lambda: self.camera_thread is not None,
            )
            controls_layout.addWidget(self.stage_module.panel)

        self.display_panel = DisplayPanel()
        controls_layout.addWidget(self.display_panel)
        controls_layout.addStretch()
        # Wide enough for the longest label in the active language (translations
        # can be longer than English), but never narrower than 280 px. The
        # language is fixed for the whole run, so this is computed once.
        controls.setFixedWidth(max(280, controls.minimumSizeHint().width()))

        self.status = QStatusBar()
        self.setStatusBar(self.status)
        if self.stage_module is not None:
            self.stage_module.status_message.connect(self.status.showMessage)
        if self.mode is AppMode.SIMULATION:
            self.status.showMessage(_("SIMULATION MODE"))
        elif self.mode is AppMode.CAMERA_ONLY:
            self.status.showMessage(_("CAMERA-ONLY MODE"))
        else:
            port = getattr(stage, "port", None)
            self.status.showMessage(_("Stage connected ({port})").format(port=port) if port else _("Stage connected"))

    # ----------------------------------------------------- Camera handling --
    def _detect_camera_names(self) -> None:
        result = detect_camera_names()
        if not result.supported:
            QMessageBox.information(
                self, _("Windows only"),
                _(
                    "Name detection uses DirectShow and only works on Windows.\n\n"
                    "Just try device index 0, 1, 2... in the spinbox and click "
                    "Start Stream to find the right one."
                ),
            )
            return
        if result.error:
            QMessageBox.information(self, _("Camera name detection"), result.error)
            return
        if not result.names:
            QMessageBox.information(self, _("No cameras found"), _("No DirectShow camera devices were detected."))
            return
        lines = "\n".join(f"  {i}: {name}" for i, name in enumerate(result.names))
        QMessageBox.information(
            self, _("Detected cameras"),
            _(
                "Device order seen by Windows (usually matches the index used "
                "here, regardless of which backend you stream with):\n\n{lines}\n\n"
                "Set the Device index spinbox above to the number next to your "
                "camera's name, then click Start Stream."
            ).format(lines=lines),
        )

    def _start_stream(self) -> None:
        device_index = self.camera_panel.device_index
        resolution = self.camera_panel.resolution
        backend = self.camera_panel.backend

        self.video_label.setFixedSize(resolution.width, resolution.height)
        self.flash_overlay.setGeometry(self.video_label.rect())
        self.camera_thread = CameraThread(device_index, resolution.width, resolution.height, backend.cv2_flag)
        self.camera_thread.frame_ready.connect(self._on_frame)
        self.camera_thread.error_occurred.connect(self._on_error)
        self.camera_thread.start()

        self.camera_panel.set_streaming(True)
        self.frame_count = 0
        self.status.showMessage(_("Streaming..."))

    def _stop_stream(self) -> None:
        if self.camera_thread is not None:
            self.camera_thread.stop()
            self.camera_thread = None
        if self.video_writer is not None:
            self._toggle_recording()  # cleanly closes the file
        self.camera_panel.set_streaming(False)
        self.video_label.setText(_("Camera stopped"))
        self.video_label.setPixmap(QPixmap())
        self.status.showMessage(_("Idle"))

    def _on_error(self, kind: str, message: str) -> None:
        """No modal dialog: the image box itself says what happened, so the
        user can just change the device index and press Start Stream again."""
        self._stop_stream()
        headline = {
            ERR_NOT_DETECTED: _("Camera not detected"),
            ERR_LOST: _("Camera disconnected"),
        }.get(kind, _("Camera error"))
        self.video_label.setText(f"{headline}\n\n{message}")
        self.status.showMessage(f"{headline}: {message}")

    def _on_frame(self, frame: np.ndarray, fps: float) -> None:
        self.frame_count += 1
        self.last_frame = frame  # raw frame, used as the basis for exports

        recorded_frame = self._draw_overlays(frame.copy())
        if self.video_writer is not None:
            self.video_writer.write(recorded_frame)

        # Grid and the blinking "REC" dot are live-preview aids only - both
        # are overlaid after writing so neither ends up baked into the
        # saved video/snapshot (the scale bar, by contrast, is meaningful
        # measurement data and *is* baked in - see _draw_overlays).
        display_frame = recorded_frame
        needs_copy = self.display_panel.show_grid or (self.video_writer is not None and self._recording_blink_on)
        if needs_copy:
            display_frame = recorded_frame.copy()
        if self.display_panel.show_grid:
            display_frame = draw_grid(display_frame, self.display_panel.grid_spacing_px)
        if self.video_writer is not None and self._recording_blink_on:
            cv2.circle(display_frame, (24, 24), 9, (0, 0, 255), -1, cv2.LINE_AA)
            cv2.putText(
                display_frame, "REC", (40, 32),
                cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2, cv2.LINE_AA,
            )

        rgb = cv2.cvtColor(display_frame, cv2.COLOR_BGR2RGB)
        h, w, ch = rgb.shape
        qimg = QImage(rgb.data, w, h, ch * w, QImage.Format_RGB888)
        self.video_label.setPixmap(QPixmap.fromImage(qimg))

        self.status.showMessage(_("Frame {count} | {fps:.1f} fps").format(count=self.frame_count, fps=fps))

    def _draw_overlays(self, frame: np.ndarray) -> np.ndarray:
        if self.display_panel.show_scale_bar:
            frame = draw_scale_bar(frame, self.display_panel.um_per_pixel_override)
        if self.capture_panel.burn_timestamp:
            ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
            cv2.putText(
                frame, ts, (10, frame.shape[0] - 12),
                cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 220, 90), 1, cv2.LINE_AA,
            )
        return frame

    def _toggle_recording_blink(self) -> None:
        self._recording_blink_on = not self._recording_blink_on

    # -------------------------------------------------------------- Export --
    def _choose_output_dir(self) -> None:
        directory = QFileDialog.getExistingDirectory(self, _("Choose output folder"), str(self._output_dir))
        if directory:
            self._output_dir = Path(directory)
            self.capture_panel.set_output_dir_text(self._output_dir)

    def _save_snapshot(self) -> None:
        if self.last_frame is None:
            self.status.showMessage(_("No frame to save yet."))
            return
        frame = self._draw_overlays(self.last_frame.copy())
        self.snapshot_count += 1
        ts = datetime.now().strftime("%Y%m%d_%H%M%S_%f")[:-3]
        filename = self._output_dir / f"frame_{ts}.png"
        cv2.imwrite(str(filename), frame)
        self.status.showMessage(_("Saved {filename}  ({count} total)").format(filename=filename, count=self.snapshot_count))
        self._flash_snapshot()

    def _flash_snapshot(self) -> None:
        self.flash_overlay.setGeometry(self.video_label.rect())
        self.flash_overlay.show()
        self.flash_overlay.raise_()
        QTimer.singleShot(SNAPSHOT_FLASH_MS, self.flash_overlay.hide)

    def _toggle_recording(self) -> None:
        if self.video_writer is None:
            if self.last_frame is None:
                QMessageBox.information(self, _("Start stream first"), _("Start the camera stream before recording."))
                return
            h, w = self.last_frame.shape[:2]
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            path = self._output_dir / f"recording_{ts}.mp4"
            fourcc = cv2.VideoWriter_fourcc(*"mp4v")
            self.video_writer = cv2.VideoWriter(str(path), fourcc, 20.0, (w, h))
            self.capture_panel.set_recording(True)
            self._recording_blink_on = True
            self.recording_blink_timer.start(RECORDING_BLINK_INTERVAL_MS)
            self.status.showMessage(_("Recording to {path}").format(path=path))
        else:
            self.video_writer.release()
            self.video_writer = None
            self.recording_blink_timer.stop()
            self._recording_blink_on = False
            self.capture_panel.set_recording(False)
            self.status.showMessage(_("Recording stopped"))

    # ------------------------------------------------------------- Cleanup --
    def closeEvent(self, event) -> None:
        self._stop_stream()
        if hasattr(self, "recording_blink_timer"):
            self.recording_blink_timer.stop()
        if self.stage_module is not None:
            self.stage_module.shutdown()
        event.accept()
