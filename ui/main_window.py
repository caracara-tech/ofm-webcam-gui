"""Top-level QMainWindow. Wires panels + background threads together.

Deliberately thin: camera I/O lives in CameraThread, stage math lives in
core.stage_motion, stage backends live in hardware.stage. This class's job
is UI composition and event routing only.
"""

from __future__ import annotations

import logging
import platform
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

from core.config import DEFAULT_OUTPUT_DIR, SANGABOARD_MAX_STEPS_PER_SEC
from core.stage_motion import plan_jog
from core.types import Direction, StageMotionSettings
from hardware.stage import SangaboardStageController, StageInitResult, create_stage_controller
from panels.camera_panel import CameraPanel
from panels.capture_panel import CapturePanel
from panels.stage_panel import StagePanel
from threads.camera_thread import CameraThread
from threads.stage_thread import StageMovementThread

logger = logging.getLogger(__name__)

POSITION_POLL_INTERVAL_MS = 100
APP_TITLE = "OFM Webcam Viewer v0.1"


class MainWindow(QMainWindow):
    def __init__(self, simulation_mode: bool = False):
        super().__init__()

        self._output_dir = DEFAULT_OUTPUT_DIR
        self._output_dir.mkdir(parents=True, exist_ok=True)

        self.camera_thread: Optional[CameraThread] = None
        self.video_writer: Optional[cv2.VideoWriter] = None
        self.last_frame: Optional[np.ndarray] = None
        self.frame_count = 0
        self.snapshot_count = 0

        stage_init: StageInitResult = create_stage_controller(simulate=simulation_mode)
        self.stage = stage_init.controller
        self.simulation_mode = stage_init.simulation_mode
        self.simulation_reason = stage_init.simulation_reason

        self.stage_settings = StageMotionSettings()

        self.setWindowTitle(APP_TITLE + (" [SIMULATION]" if self.simulation_mode else ""))
        self.resize(900, 700)

        self._build_ui()

        self.stage_thread = StageMovementThread()
        self.stage_thread.movement_complete.connect(self._on_movement_complete)
        self.stage_thread.start()

        self.position_timer = QTimer(self)
        self.position_timer.timeout.connect(self._update_position_display)
        self.position_timer.start(POSITION_POLL_INTERVAL_MS)
        self._update_position_display()

    # ---------------------------------------------------------------- UI ---
    def _build_ui(self) -> None:
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QHBoxLayout(central)

        self.video_label = QLabel()
        self.video_label.setAlignment(Qt.AlignCenter)
        self.video_label.setStyleSheet("background-color: #111; color: #888;")
        self.video_label.setText("Camera stopped")
        self.video_label.setMinimumSize(640, 480)
        main_layout.addWidget(self.video_label, stretch=3)

        controls = QWidget()
        controls.setFixedWidth(280)
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

        self.stage_panel = StagePanel(self.stage_settings)
        self.stage_panel.jog_requested.connect(self._on_jog_requested)
        self.stage_panel.settings_changed.connect(self._on_stage_settings_changed)
        if self.stage is None:
            self.stage_panel.set_enabled_all(False)
        controls_layout.addWidget(self.stage_panel)
        controls_layout.addStretch()

        self.status = QStatusBar()
        self.setStatusBar(self.status)
        if self.simulation_mode:
            if self.simulation_reason == "not detected":
                self.status.showMessage("SIMULATION MODE: Stage controller not detected, using mock controller")
            else:
                self.status.showMessage("SIMULATION MODE: User requested simulation mode")
        else:
            self.status.showMessage("Idle")

    # ----------------------------------------------------- Camera handling --
    def _detect_camera_names(self) -> None:
        if platform.system() != "Windows":
            QMessageBox.information(
                self, "Windows only",
                "Name detection uses DirectShow and only works on Windows.\n\n"
                "Just try device index 0, 1, 2... in the spinbox and click "
                "Start Stream to find the right one.",
            )
            return
        try:
            from pygrabber.dshow_graph import FilterGraph
        except ImportError:
            QMessageBox.information(
                self, "Optional package needed",
                "Install pygrabber to auto-detect camera names:\n\n"
                "    pip install pygrabber\n\n"
                "Then click this button again. In the meantime, just try "
                "device index 0, 1, 2... in the spinbox and click Start "
                "Stream to find your webcam.",
            )
            return
        try:
            names = FilterGraph().get_input_devices()
        except Exception as exc:
            QMessageBox.warning(self, "Detection failed", f"Could not list camera devices: {exc}")
            return
        if not names:
            QMessageBox.information(self, "No cameras found", "No DirectShow camera devices were detected.")
            return
        lines = "\n".join(f"  {i}: {name}" for i, name in enumerate(names))
        QMessageBox.information(
            self, "Detected cameras",
            f"Device order seen by Windows (usually matches the index used "
            f"here, regardless of which backend you stream with):\n\n{lines}\n\n"
            f"Set the Device index spinbox above to the number next to your "
            f"camera's name, then click Start Stream.",
        )

    def _start_stream(self) -> None:
        device_index = self.camera_panel.device_index
        resolution = self.camera_panel.resolution
        backend = self.camera_panel.backend

        self.video_label.setFixedSize(resolution.width, resolution.height)
        self.camera_thread = CameraThread(device_index, resolution.width, resolution.height, backend.cv2_flag)
        self.camera_thread.frame_ready.connect(self._on_frame)
        self.camera_thread.error_occurred.connect(self._on_error)
        self.camera_thread.start()

        self.camera_panel.set_streaming(True)
        self.frame_count = 0
        self.status.showMessage("Streaming...")

    def _stop_stream(self) -> None:
        if self.camera_thread is not None:
            self.camera_thread.stop()
            self.camera_thread = None
        if self.video_writer is not None:
            self._toggle_recording()  # cleanly closes the file
        self.camera_panel.set_streaming(False)
        self.video_label.setText("Camera stopped")
        self.video_label.setPixmap(QPixmap())
        self.status.showMessage("Idle")

    def _on_error(self, message: str) -> None:
        QMessageBox.critical(self, "Camera error", message)
        self._stop_stream()

    def _on_frame(self, frame: np.ndarray, fps: float) -> None:
        self.frame_count += 1
        self.last_frame = frame  # raw frame, used as the basis for exports

        display_frame = self._draw_overlays(frame.copy())

        rgb = cv2.cvtColor(display_frame, cv2.COLOR_BGR2RGB)
        h, w, ch = rgb.shape
        qimg = QImage(rgb.data, w, h, ch * w, QImage.Format_RGB888)
        self.video_label.setPixmap(QPixmap.fromImage(qimg))

        if self.video_writer is not None:
            self.video_writer.write(display_frame)

        self.status.showMessage(f"Frame {self.frame_count} | {fps:.1f} fps")

    def _draw_overlays(self, frame: np.ndarray) -> np.ndarray:
        if self.capture_panel.burn_timestamp:
            ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
            cv2.putText(
                frame, ts, (10, frame.shape[0] - 12),
                cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 220, 90), 1, cv2.LINE_AA,
            )
        return frame

    # -------------------------------------------------------------- Export --
    def _choose_output_dir(self) -> None:
        directory = QFileDialog.getExistingDirectory(self, "Choose output folder", str(self._output_dir))
        if directory:
            self._output_dir = Path(directory)
            self.capture_panel.set_output_dir_text(self._output_dir)

    def _save_snapshot(self) -> None:
        if self.last_frame is None:
            self.status.showMessage("No frame to save yet.")
            return
        frame = self._draw_overlays(self.last_frame.copy())
        self.snapshot_count += 1
        ts = datetime.now().strftime("%Y%m%d_%H%M%S_%f")[:-3]
        filename = self._output_dir / f"frame_{ts}.png"
        cv2.imwrite(str(filename), frame)
        self.status.showMessage(f"Saved {filename}  ({self.snapshot_count} total)")

    def _toggle_recording(self) -> None:
        if self.video_writer is None:
            if self.last_frame is None:
                QMessageBox.information(self, "Start stream first", "Start the camera stream before recording.")
                return
            h, w = self.last_frame.shape[:2]
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            path = self._output_dir / f"recording_{ts}.mp4"
            fourcc = cv2.VideoWriter_fourcc(*"mp4v")
            self.video_writer = cv2.VideoWriter(str(path), fourcc, 20.0, (w, h))
            self.capture_panel.set_recording(True)
            self.status.showMessage(f"Recording to {path}")
        else:
            self.video_writer.release()
            self.video_writer = None
            self.capture_panel.set_recording(False)
            self.status.showMessage("Recording stopped")

    # ------------------------------------------------------------- Cleanup --
    def closeEvent(self, event) -> None:
        self._stop_stream()
        if self.stage_thread is not None:
            self.stage_thread.stop()
        if hasattr(self, "position_timer"):
            self.position_timer.stop()
        if self.stage is not None:
            self.stage.disconnect()
        event.accept()

    # ------------------------------------------------------- Stage Control --
    def _on_stage_settings_changed(self, settings: StageMotionSettings) -> None:
        self.stage_settings = settings

    def _on_jog_requested(self, direction: Direction) -> None:
        if self.stage is None or not self.stage.is_connected():
            self.status.showMessage("Stage not connected")
            return

        steps_per_sec_limit = (
            SANGABOARD_MAX_STEPS_PER_SEC if isinstance(self.stage, SangaboardStageController) else None
        )

        plan = plan_jog(
            direction, self.stage_settings, self.stage.calibration,
            steps_per_sec_limit=steps_per_sec_limit,
        )
        if plan.steps <= 0:
            return

        if hasattr(self.stage, "set_step_delay"):
            self.stage.set_step_delay(int(plan.delay_per_step_s * 1e6))

        self.stage_thread.add_movement(
            self.stage, direction, plan.steps, plan.delay_per_step_s,
            f"Moved {direction.value} {plan.distance_um:.1f} \u00b5m",
        )

    def _update_position_display(self) -> None:
        if self.stage is not None and self.stage.is_connected():
            self.stage_panel.update_position_display(self.stage.get_position_um())

    def _on_movement_complete(self, message: str) -> None:
        self.status.showMessage(message)
        self._update_position_display()
