#!/usr/bin/env python3
"""
Webcam Snapshot & Recorder — Logitech C270
=============================================

A minimal PyQt5 + OpenCV app for streaming a webcam and saving snapshots
or recordings. No device auto-scanning on startup (that's what made the
full "lab tool" version slow to open) — you just pick a device index and
hit Start.

Snapshots and recordings are saved to the "gallery" folder in the project
directory by default.

Install dependencies:
    pip install PyQt5 opencv-python numpy

Optional (Windows only, lets you see camera names instead of guessing
index numbers — click "Detect Camera Names" in the app):
    pip install pygrabber

Run:
    python webcam_viewer.py

Notes:
  - Multiple cameras (e.g. a laptop's built-in webcam plus the C270 over
    USB) means index 0 might be the wrong one. Use the "Detect Camera
    Names" button (Windows) to see which index maps to which device name,
    or just try 0, 1, 2... in the spinbox until the right feed shows up.
  - Backend defaults to Media Foundation (MSMF) on Windows, which tends to
    be more reliable than DirectShow on Windows 10/11. If the stream
    doesn't start, try "DirectShow" from the dropdown.
"""

import sys
import os
import time
import platform
import argparse
from datetime import datetime

import cv2
import numpy as np

# Import stage controller
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from hardware.stage import SangaboardStageController, MockStageController

# Quiet OpenCV's internal backend-probing log spam.
try:
    cv2.utils.logging.setLogLevel(cv2.utils.logging.LOG_LEVEL_ERROR)
except Exception:
    pass

from PyQt5.QtCore import Qt, QThread, pyqtSignal, QMutex, QTimer
from PyQt5.QtGui import QImage, QPixmap
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QLabel, QPushButton, QComboBox,
    QSpinBox, QCheckBox, QVBoxLayout, QHBoxLayout, QGridLayout,
    QFileDialog, QGroupBox, QLineEdit, QMessageBox, QStatusBar
)

RESOLUTIONS = [
    ("1280 x 720", 1280, 720),
    ("960 x 544", 960, 544),
    ("800 x 600", 800, 600),
    ("640 x 480", 640, 480),
    ("320 x 240", 320, 240),
]

BACKENDS = [
    ("Auto", None),
    ("Media Foundation - MSMF (Windows, recommended)", cv2.CAP_MSMF),
    ("DirectShow - DSHOW (Windows, fallback)", cv2.CAP_DSHOW),
    ("V4L2 (Linux)", cv2.CAP_V4L2),
]


def default_backend_index():
    system = platform.system()
    if system == "Windows":
        return 1  # Media Foundation
    if system == "Linux":
        return 3  # V4L2
    return 0  # Auto (macOS / unknown)


class StageMovementThread(QThread):
    """Handles stage movements in a background thread to avoid blocking UI."""

    movement_complete = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self._queue = []
        self._mutex = QMutex()
        self._running = False

    def add_movement(self, stage, cmd, steps, delay_s, status_msg):
        self._mutex.lock()
        self._queue.append((stage, cmd, steps, delay_s, status_msg))
        self._mutex.unlock()

    def run(self):
        self._running = True
        while self._running:
            self._mutex.lock()
            if self._queue:
                stage, cmd, steps, delay_s, status_msg = self._queue.pop(0)
                self._mutex.unlock()
                try:
                    stage.move_steps(cmd, steps, delay_s)
                    self.movement_complete.emit(status_msg)
                except Exception as e:
                    self.movement_complete.emit(f"Error: {e}")
            else:
                self._mutex.unlock()
                self.msleep(10)

    def stop(self):
        self._running = False
        self.wait(2000)


class CameraThread(QThread):
    """Reads frames from the camera in a background thread."""

    frame_ready = pyqtSignal(np.ndarray, float)
    error_occurred = pyqtSignal(str)

    def __init__(self, device_index, width, height, backend_flag, target_fps=30):
        super().__init__()
        self.device_index = device_index
        self.width = width
        self.height = height
        self.backend_flag = backend_flag
        self.target_fps = target_fps
        self._running = False

    def run(self):
        self._running = True
        try:
            cap = self._open_capture()
            if cap is None or not cap.isOpened():
                self.error_occurred.emit(
                    f"Could not open camera at index {self.device_index}. "
                    f"Try a different device index or backend."
                )
                return

            cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.width)
            cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.height)
            cap.set(cv2.CAP_PROP_FPS, self.target_fps)

            # Brief warm-up: some backends (esp. MSMF) need a moment before
            # the first frame is actually deliverable.
            warm_up_ok = False
            for _ in range(20):
                if not self._running:
                    cap.release()
                    return
                ret, _ = cap.read()
                if ret:
                    warm_up_ok = True
                    break
                time.sleep(0.1)

            if not warm_up_ok:
                self.error_occurred.emit(
                    f"Camera opened but never delivered a frame at index "
                    f"{self.device_index}. It may be in use by another app, "
                    f"or need a different backend."
                )
                cap.release()
                return

            last_time = time.time()
            while self._running:
                ret, frame = cap.read()
                if not ret:
                    self.error_occurred.emit("Lost connection to camera (no frame).")
                    break
                now = time.time()
                dt = now - last_time
                last_time = now
                fps = 1.0 / dt if dt > 0 else 0.0
                self.frame_ready.emit(frame, fps)

            cap.release()
        except Exception as exc:
            self.error_occurred.emit(str(exc))

    def _open_capture(self):
        if self.backend_flag is None:
            return cv2.VideoCapture(self.device_index)
        cap = cv2.VideoCapture(self.device_index, self.backend_flag)
        if cap.isOpened():
            return cap
        cap.release()
        return cv2.VideoCapture(self.device_index)  # fallback to Auto

    def stop(self):
        self._running = False
        self.wait(2000)


class MainWindow(QMainWindow):
    def __init__(self, simulation_mode=False):
        super().__init__()
        mode_suffix = " [SIMULATION]" if simulation_mode else ""
        self.setWindowTitle(f"OFM Webcam Viewer v0.0{mode_suffix}")
        self.resize(900, 700)

        self.camera_thread = None
        self.video_writer = None
        self.last_frame = None
        self.frame_count = 0
        self.snapshot_count = 0
        self.output_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "gallery")
        os.makedirs(self.output_dir, exist_ok=True)

        # Stage controller initialization
        self.stage = None
        self.simulation_mode = simulation_mode
        self.simulation_reason = None
        
        if simulation_mode:
            print("Starting in SIMULATION mode (user requested)")
            self.simulation_reason = "user requested"
            self.stage = MockStageController(simulation_speed_multiplier=10.0)
            self.stage.connect()
        else:
            try:
                self.stage = SangaboardStageController(port='COM5', timeout=2)
                self.stage.connect()
                if not self.stage.is_connected():
                    raise Exception("Connection failed")
            except Exception as e:
                print(f"Could not connect to stage: {e}")
                print("Falling back to SIMULATION mode")
                self.simulation_mode = True
                self.simulation_reason = "not detected"
                self.stage = MockStageController(simulation_speed_multiplier=10.0)
                self.stage.connect()

        # Stage control state variables
        self.manual_xy_step = 10.0  # microns
        self.manual_z_step = 1.0    # microns
        self.stage_speed_um_s = 100.0  # um/s
        self.bed_correction_enabled = False

        self._build_ui()

        # Stage movement thread (initialized after UI is built)
        self.stage_thread = StageMovementThread()
        self.stage_thread.movement_complete.connect(self._on_movement_complete)
        self.stage_thread.start()
        
        # Position update timer (updates every 100ms for live display)
        self.position_timer = QTimer()
        self.position_timer.timeout.connect(self._update_position_display)
        self.position_timer.start(100)
        
        # Initial position update
        self._update_position_display()

    # ---------------------------------------------------------------- UI ---
    def _build_ui(self):
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

        # --- Camera group ---
        cam_group = QGroupBox("Camera")
        cam_layout = QGridLayout(cam_group)

        cam_layout.addWidget(QLabel("Device index:"), 0, 0)
        self.device_spin = QSpinBox()
        self.device_spin.setRange(0, 9)
        self.device_spin.setValue(0)
        cam_layout.addWidget(self.device_spin, 0, 1)

        self.detect_names_btn = QPushButton("Detect Camera Names (Windows)")
        self.detect_names_btn.clicked.connect(self._detect_camera_names)
        cam_layout.addWidget(self.detect_names_btn, 1, 0, 1, 2)

        cam_layout.addWidget(QLabel("Backend:"), 2, 0)
        self.backend_combo = QComboBox()
        for name, _ in BACKENDS:
            self.backend_combo.addItem(name)
        self.backend_combo.setCurrentIndex(default_backend_index())
        cam_layout.addWidget(self.backend_combo, 2, 1)

        cam_layout.addWidget(QLabel("Resolution:"), 3, 0)
        self.resolution_combo = QComboBox()
        for name, _, _ in RESOLUTIONS:
            self.resolution_combo.addItem(name)
        cam_layout.addWidget(self.resolution_combo, 3, 1)

        self.start_btn = QPushButton("Start Stream")
        self.start_btn.clicked.connect(self._toggle_stream)
        cam_layout.addWidget(self.start_btn, 4, 0, 1, 2)

        controls_layout.addWidget(cam_group)

        # --- Capture group ---
        capture_group = QGroupBox("Snapshots & Recording")
        capture_layout = QGridLayout(capture_group)

        capture_layout.addWidget(QLabel("Output folder:"), 0, 0, 1, 2)
        self.output_edit = QLineEdit(self.output_dir)
        self.output_edit.setReadOnly(True)
        capture_layout.addWidget(self.output_edit, 1, 0)
        browse_btn = QPushButton("Browse")
        browse_btn.clicked.connect(self._choose_output_dir)
        capture_layout.addWidget(browse_btn, 1, 1)

        self.timestamp_chk = QCheckBox("Burn timestamp into frame")
        self.timestamp_chk.setChecked(True)
        capture_layout.addWidget(self.timestamp_chk, 2, 0, 1, 2)

        self.snapshot_btn = QPushButton("Save Snapshot (PNG)")
        self.snapshot_btn.clicked.connect(self._save_snapshot)
        capture_layout.addWidget(self.snapshot_btn, 3, 0, 1, 2)

        self.record_btn = QPushButton("Start Recording (.mp4)")
        self.record_btn.clicked.connect(self._toggle_recording)
        capture_layout.addWidget(self.record_btn, 4, 0, 1, 2)

        controls_layout.addWidget(capture_group)

        # --- Stage Control group ---
        stage_group = QGroupBox("Stage Control")
        stage_layout = QGridLayout(stage_group)

        # Direction buttons
        btn_layout = [
            ('U', 0, 1), ('D', 1, 1),
            ('L', 1, 0), ('R', 1, 2),
            ('W ↑', 0, 3), ('S ↓', 1, 3)
        ]
        for txt, r, c in btn_layout:
            cmd = txt[0]
            btn = QPushButton(txt)
            btn.clicked.connect(lambda checked, c=cmd: self.move_stage(c))
            # Set appropriate width based on button text length
            if len(txt) > 2:  # W ↑ and S ↓ buttons
                btn.setMaximumWidth(60)
            else:  # U, D, L, R buttons
                btn.setMaximumWidth(60)
            stage_layout.addWidget(btn, r, c)

        # Manual Step Sizes
        stage_layout.addWidget(QLabel("XY Step (µm):"), 2, 0, 1, 2)
        self.xy_step_spin = QSpinBox()
        self.xy_step_spin.setRange(1, 1000)
        self.xy_step_spin.setValue(int(self.manual_xy_step))
        self.xy_step_spin.valueChanged.connect(self._update_xy_step)
        stage_layout.addWidget(self.xy_step_spin, 2, 2, 1, 2)

        stage_layout.addWidget(QLabel("Z Step (µm):"), 3, 0, 1, 2)
        self.z_step_spin = QSpinBox()
        self.z_step_spin.setRange(1, 1000)
        self.z_step_spin.setValue(int(self.manual_z_step))
        self.z_step_spin.valueChanged.connect(self._update_z_step)
        stage_layout.addWidget(self.z_step_spin, 3, 2, 1, 2)

        stage_layout.addWidget(QLabel("Speed (µm/s):"), 4, 0, 1, 2)
        self.speed_spin = QSpinBox()
        self.speed_spin.setRange(1, 1000)
        self.speed_spin.setValue(int(self.stage_speed_um_s))
        self.speed_spin.valueChanged.connect(self._update_speed)
        stage_layout.addWidget(self.speed_spin, 4, 2, 1, 2)

        # Position Display
        stage_layout.addWidget(QLabel("Position (µm):"), 5, 0, 1, 2)
        pos_layout = QHBoxLayout()
        self.pos_x_label = QLabel("X: 0.00")
        self.pos_y_label = QLabel("Y: 0.00")
        self.pos_z_label = QLabel("Z: 0.00")
        pos_layout.addWidget(self.pos_x_label)
        pos_layout.addWidget(self.pos_y_label)
        pos_layout.addWidget(self.pos_z_label)
        stage_layout.addLayout(pos_layout, 6, 0, 1, 4)

        # Bed Correction Checkbox
        self.bed_check = QCheckBox("Auto-Level Z")
        self.bed_check.setChecked(self.bed_correction_enabled)
        self.bed_check.toggled.connect(self._update_bed_correction)
        stage_layout.addWidget(self.bed_check, 7, 0, 1, 4)

        # Disable stage controls only if stage is completely unavailable
        # (simulation mode is always available)
        if self.stage is None:
            for i in range(stage_layout.count()):
                widget = stage_layout.itemAt(i).widget()
                if widget is not None:
                    widget.setEnabled(False)

        controls_layout.addWidget(stage_group)
        controls_layout.addStretch()

        self.status = QStatusBar()
        self.setStatusBar(self.status)
        
        # Show simulation mode message if applicable
        if self.simulation_mode:
            if self.simulation_reason == "not detected":
                self.status.showMessage("SIMULATION MODE: Stage controller not detected, using mock controller")
            else:
                self.status.showMessage("SIMULATION MODE: User requested simulation mode")
        else:
            self.status.showMessage("Idle")

    # ----------------------------------------------------- Camera handling --
    def _detect_camera_names(self):
        if platform.system() != "Windows":
            QMessageBox.information(
                self, "Windows only",
                "Name detection uses DirectShow and only works on Windows.\n\n"
                "Just try device index 0, 1, 2... in the spinbox and click "
                "Start Stream to find the right one."
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
                "Stream to find your webcam."
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
            f"camera's name, then click Start Stream."
        )

    def _toggle_stream(self):
        if self.camera_thread is None:
            self._start_stream()
        else:
            self._stop_stream()

    def _start_stream(self):
        device_index = self.device_spin.value()
        _, w, h = RESOLUTIONS[self.resolution_combo.currentIndex()]
        backend_flag = BACKENDS[self.backend_combo.currentIndex()][1]

        self.video_label.setFixedSize(w, h)
        self.camera_thread = CameraThread(device_index, w, h, backend_flag)
        self.camera_thread.frame_ready.connect(self._on_frame)
        self.camera_thread.error_occurred.connect(self._on_error)
        self.camera_thread.start()

        self.start_btn.setText("Stop Stream")
        self.frame_count = 0
        self.status.showMessage("Streaming...")

    def _stop_stream(self):
        if self.camera_thread is not None:
            self.camera_thread.stop()
            self.camera_thread = None
        if self.video_writer is not None:
            self._toggle_recording()  # cleanly closes the file
        self.start_btn.setText("Start Stream")
        self.video_label.setText("Camera stopped")
        self.video_label.setPixmap(QPixmap())
        self.status.showMessage("Idle")

    def _on_error(self, message):
        QMessageBox.critical(self, "Camera error", message)
        self._stop_stream()

    def _on_frame(self, frame, fps):
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

    def _draw_overlays(self, frame):
        if self.timestamp_chk.isChecked():
            ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
            cv2.putText(
                frame, ts, (10, frame.shape[0] - 12),
                cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 220, 90), 1, cv2.LINE_AA,
            )
        return frame

    # -------------------------------------------------------------- Export --
    def _choose_output_dir(self):
        directory = QFileDialog.getExistingDirectory(self, "Choose output folder", self.output_dir)
        if directory:
            self.output_dir = directory
            self.output_edit.setText(directory)

    def _save_snapshot(self):
        if self.last_frame is None:
            self.status.showMessage("No frame to save yet.")
            return
        frame = self._draw_overlays(self.last_frame.copy())
        self.snapshot_count += 1
        ts = datetime.now().strftime("%Y%m%d_%H%M%S_%f")[:-3]
        filename = os.path.join(self.output_dir, f"frame_{ts}.png")
        cv2.imwrite(filename, frame)
        self.status.showMessage(f"Saved {filename}  ({self.snapshot_count} total)")

    def _toggle_recording(self):
        if self.video_writer is None:
            if self.last_frame is None:
                QMessageBox.information(self, "Start stream first",
                                         "Start the camera stream before recording.")
                return
            h, w = self.last_frame.shape[:2]
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            path = os.path.join(self.output_dir, f"recording_{ts}.mp4")
            fourcc = cv2.VideoWriter_fourcc(*"mp4v")
            self.video_writer = cv2.VideoWriter(path, fourcc, 20.0, (w, h))
            self.record_btn.setText("Stop Recording")
            self.status.showMessage(f"Recording to {path}")
        else:
            self.video_writer.release()
            self.video_writer = None
            self.record_btn.setText("Start Recording (.mp4)")
            self.status.showMessage("Recording stopped")

    # ------------------------------------------------------------- Cleanup --
    def closeEvent(self, event):
        self._stop_stream()
        if self.stage_thread is not None:
            self.stage_thread.stop()
        if hasattr(self, 'position_timer'):
            self.position_timer.stop()
        if self.stage is not None:
            self.stage.disconnect()
        event.accept()

    # ------------------------------------------------------- Stage Control --
    def move_stage(self, cmd):
        """Moves stage by the step size specified in the UI (in µm)."""
        if self.stage is None or not self.stage.is_connected():
            self.status.showMessage("Stage not connected")
            return

        step_x_um = self.manual_xy_step
        step_y_um = self.manual_xy_step
        step_z_um = self.manual_z_step

        axis = 'z'
        dist_um = 0

        if cmd == 'L':
            axis = 'x'; dist_um = -step_x_um
        elif cmd == 'R':
            axis = 'x'; dist_um = step_x_um
        elif cmd == 'U':
            axis = 'y'; dist_um = step_y_um
        elif cmd == 'D':
            axis = 'y'; dist_um = -step_y_um
        elif cmd == 'W':
            axis = 'z'; dist_um = step_z_um
        elif cmd == 'S':
            axis = 'z'; dist_um = -step_z_um

        steps = self.stage.um_to_steps(abs(dist_um), axis)
        if steps > 0:
            final_cmd = cmd

            # Calculate Delay from Speed
            speed_um_s = self.stage_speed_um_s
            if speed_um_s <= 0.1:
                speed_um_s = 0.1  # Minimum speed safety

            # Get scale for axis
            scale_nm = 100.0  # fallback
            if axis == 'x':
                scale_nm = self.stage.scale_nm_per_step_x
            elif axis == 'y':
                scale_nm = self.stage.scale_nm_per_step_y
            elif axis == 'z':
                scale_nm = self.stage.scale_nm_per_step_z

            # steps/s = (speed_um_s * 1000 nm/um) / scale_nm
            steps_per_sec = (speed_um_s * 1000.0) / scale_nm

            # Sangaboard Limit: Max 1000 steps/s
            if "Sangaboard" in str(type(self.stage)) and steps_per_sec > 1000:
                steps_per_sec = 1000

            delay_s = 1.0 / steps_per_sec if steps_per_sec > 0 else 0.1

            # Set delay if supported (Sangaboard)
            if hasattr(self.stage, 'set_step_delay'):
                self.stage.set_step_delay(int(delay_s * 1e6))

            # Queue movement to background thread instead of blocking UI
            self.stage_thread.add_movement(
                self.stage, final_cmd, steps, delay_s,
                f"Moved {cmd} {dist_um:.1f} µm"
            )

    def _update_xy_step(self, value):
        self.manual_xy_step = float(value)

    def _update_z_step(self, value):
        self.manual_z_step = float(value)

    def _update_speed(self, value):
        self.stage_speed_um_s = float(value)

    def _update_bed_correction(self, checked):
        self.bed_correction_enabled = checked
        if self.stage is not None:
            self.stage.backlash_enabled = checked

    def _update_position_display(self):
        """Update the position labels with current stage position."""
        if self.stage is not None and self.stage.is_connected():
            x_um, y_um, z_um = self.stage.get_position_um()
            self.pos_x_label.setText(f"X: {x_um:.2f}")
            self.pos_y_label.setText(f"Y: {y_um:.2f}")
            self.pos_z_label.setText(f"Z: {z_um:.2f}")

    def _on_movement_complete(self, message):
        """Called when stage movement completes."""
        self.status.showMessage(message)
        self._update_position_display()


def main():
    parser = argparse.ArgumentParser(description='OFM Webcam Viewer')
    parser.add_argument('--simulate', action='store_true', 
                        help='Run in simulation mode (mock stage controller)')
    args = parser.parse_args()
    
    app = QApplication(sys.argv)
    window = MainWindow(simulation_mode=args.simulate)
    window.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
