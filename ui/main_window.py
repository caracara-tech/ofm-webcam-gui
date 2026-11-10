"""Top-level QMainWindow. Wires panels + background threads together.

Deliberately thin: camera I/O lives in CameraThread, stage math lives in
core.stage_motion, stage backends live in hardware.stage, log handling lives
in core.logging_setup. This class's job is UI composition and event routing only.
"""

from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path
from typing import Optional

import cv2
import numpy as np
from PyQt5.QtCore import QTimer
from PyQt5.QtGui import QImage
from PyQt5.QtWidgets import (
    QApplication, QFileDialog, QHBoxLayout, QMainWindow, QMessageBox, QPushButton, QStatusBar, QVBoxLayout, QWidget,
)

from core.app_info import LICENSE_SPDX
from core.app_mode import AppMode
from core.config import DEFAULT_OUTPUT_DIR
from core.i18n import _, current_language
from core.logging_setup import LogSession
from core.overlays import draw_grid, draw_scale_bar
from core.version import __version__
from hardware.stage import create_stage
from .dialogs.about import AboutDialog
from .dialogs.log_viewer import LogViewerDialog
from .panels.camera_panel import CameraPanel
from .panels.capture_panel import CapturePanel
from .desktop import open_in_file_manager
from .panels.display_panel import DisplayPanel
from .panels.log_panel import LogBar
from .stage_module import StageModule
from .startup import ModeDialog
from .threads.camera_thread import ERR_LOST, ERR_NOT_DETECTED, CameraThread
from .widgets.scroll_column import ScrollColumn
from .widgets.video_view import VideoView

logger = logging.getLogger(__name__)

APP_TITLE = "OFM Webcam Viewer v" + ".".join(__version__.split(".")[:2])  # e.g. "v0.1"
SNAPSHOT_FLASH_MS = 120
RECORDING_BLINK_INTERVAL_MS = 500
# On first show the window takes the size its content asks for, but never more
# than this share of the screen it opens on (so it fits 1280x720 as well as 1080p).
MAX_INITIAL_SCREEN_FRACTION = 0.9


class MainWindow(QMainWindow):
    def __init__(self, mode: AppMode, log_session: LogSession, stage_port: Optional[str] = None):
        super().__init__()
        self.mode = mode
        self._log = log_session
        self._stage_port = stage_port
        logger.info("Session started in %s mode", mode.value)

        self._output_dir = DEFAULT_OUTPUT_DIR
        self._output_dir.mkdir(parents=True, exist_ok=True)

        self.camera_thread: Optional[CameraThread] = None
        self.video_writer: Optional[cv2.VideoWriter] = None
        self.last_frame: Optional[np.ndarray] = None
        self.frame_count = 0
        self.snapshot_count = 0
        self._recording_blink_on = False

        self.stage_module: Optional[StageModule] = None
        self._screen_signal_connected = False
        self._log_viewer: Optional[LogViewerDialog] = None

        # Set when the user asks to go back to the start screen; the caller
        # (app.py) reads it after this window closes and starts that mode.
        self.next_mode: Optional[AppMode] = None

        title_suffix = _("SIMULATION") if mode is AppMode.SIMULATION else mode.label
        self.setWindowTitle(f"{APP_TITLE} - {title_suffix}")

        self._build_ui()
        self._apply_initial_size()

        self.recording_blink_timer = QTimer(self)
        self.recording_blink_timer.timeout.connect(self._toggle_recording_blink)

        # Last, once every panel and signal is wired: the window is fully up and
        # usable. The stage only starts looking for its board here if it is the
        # simulated one; a real board waits for the "Connect to stage" button.
        if self.stage_module is not None:
            self.stage_module.start()

    # ---------------------------------------------------------------- UI ---
    def _build_ui(self) -> None:
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QHBoxLayout(central)

        # Layout contract (keep it when adding widgets):
        #   * the preview takes ALL spare space and never asks for more than a
        #     constant minimum, whatever it shows (picture, error text, nothing);
        #   * the controls column takes only the width its content needs and
        #     scrolls vertically when the window is too short for it.
        # So no widget's content can resize the window or push another widget.
        self.video_view = VideoView()
        self.video_view.show_message(_("Camera stopped"))
        main_layout.addWidget(self.video_view, stretch=1)

        controls = QWidget()
        controls_layout = QVBoxLayout(controls)
        self.controls_scroll = ScrollColumn(controls)
        main_layout.addWidget(self.controls_scroll, stretch=0)

        self.change_mode_btn = QPushButton(_("Change mode / language..."))
        self.change_mode_btn.setToolTip(_("Return to the start screen to pick another mode or language"))
        self.change_mode_btn.clicked.connect(self._change_mode)
        controls_layout.addWidget(self.change_mode_btn)

        self.camera_panel = CameraPanel()
        self.camera_panel.start_stream_requested.connect(self._start_stream)
        self.camera_panel.stop_stream_requested.connect(self._stop_stream)
        controls_layout.addWidget(self.camera_panel)

        self.capture_panel = CapturePanel(self._output_dir)
        self.capture_panel.browse_requested.connect(self._choose_output_dir)
        self.capture_panel.open_folder_requested.connect(self._open_output_folder)
        self.capture_panel.snapshot_requested.connect(self._save_snapshot)
        self.capture_panel.recording_toggled.connect(self._toggle_recording)
        controls_layout.addWidget(self.capture_panel)

        stage = create_stage(self.mode, self._stage_port)  # not connected yet; StageModule does that
        if stage is not None:
            self.stage_module = StageModule(
                stage, self,
                get_frame=lambda: self.last_frame,
                get_frame_count=lambda: self.frame_count,
                is_streaming=lambda: self.camera_thread is not None,
                stage_is_real=self.mode.stage_is_real,
                # A real stage connects when the user presses the button; the
                # simulated one needs no hardware, so it is ready at once.
                auto_connect=not self.mode.stage_is_real,
            )
            controls_layout.addWidget(self.stage_module.panel)

        self.display_panel = DisplayPanel()
        # Expanding "Advanced" makes the column taller: the column scrolls, so
        # the window keeps its size; just make sure the new content is in view.
        self.display_panel.layout_changed.connect(lambda: self.controls_scroll.reveal(self.display_panel))
        controls_layout.addWidget(self.display_panel)
        controls_layout.addStretch()

        self.status = QStatusBar()
        self.setStatusBar(self.status)
        if self.stage_module is not None:
            self.stage_module.status_message.connect(self.status.showMessage)
        if self.mode is AppMode.SIMULATION:
            self.status.showMessage(_("SIMULATION MODE"))
        elif self.mode is AppMode.MANUAL:
            self.status.showMessage(_("MANUAL MODE"))

        # Log and license controls live in the status bar: always one click away,
        # and they take no height from the (already tall) controls column.
        self.log_bar = LogBar()
        self.log_bar.set_saving(self._log.saving)
        self.log_bar.save_toggled.connect(self._on_save_log_toggled)
        self.log_bar.view_requested.connect(self._show_log_viewer)
        self.status.addPermanentWidget(self.log_bar)

        self.about_btn = QPushButton(f"{_('About / License')} ({LICENSE_SPDX})")
        self.about_btn.setToolTip(_("About this program and its license"))
        self.about_btn.clicked.connect(self._show_about)
        self.status.addPermanentWidget(self.about_btn)

    def _apply_initial_size(self) -> None:
        """First-show size: what the content asks for, capped to the screen the
        window opens on. Only a starting point - the layout minimum is small
        (see _build_ui), so the user can resize freely afterwards."""
        screen = QApplication.screenAt(self.geometry().center()) or QApplication.primaryScreen()
        hint = self.sizeHint()
        if screen is None:
            self.resize(hint)
            return
        available = screen.availableGeometry()
        self.resize(
            min(hint.width(), int(available.width() * MAX_INITIAL_SCREEN_FRACTION)),
            min(hint.height(), int(available.height() * MAX_INITIAL_SCREEN_FRACTION)),
        )

    def showEvent(self, event) -> None:  # noqa: N802 (Qt naming)
        super().showEvent(event)
        handle = self.windowHandle()  # only exists once the window is shown
        if handle is not None and not self._screen_signal_connected:
            handle.screenChanged.connect(self._on_screen_changed)
            self._screen_signal_connected = True

    def _on_screen_changed(self, screen) -> None:
        """The window was dragged to another screen (other resolution and/or DPI):
        re-derive the controls' width and make sure the window still fits there."""
        self.controls_scroll.refresh_geometry()
        if screen is None or self.isMaximized() or self.isFullScreen():
            return  # the window manager sizes those itself
        available = screen.availableGeometry()
        self.resize(min(self.width(), available.width()), min(self.height(), available.height()))

    # ----------------------------------------------------- Camera handling --
    def _start_stream(self) -> None:
        device_index = self.camera_panel.device_index
        resolution = self.camera_panel.resolution
        backend = self.camera_panel.backend

        # The resolution is what the camera is asked for; the preview scales to
        # whatever room the window has and is never resized to match it.
        logger.info(
            "Starting camera stream: device index %d, %s, backend %s", device_index, resolution.label, backend.label,
        )
        self.camera_thread = CameraThread(device_index, resolution.width, resolution.height, backend.cv2_flag)
        self.camera_thread.frame_ready.connect(self._on_frame)
        self.camera_thread.error_occurred.connect(self._on_error)
        self.camera_thread.start()

        self.camera_panel.set_streaming(True)
        self.frame_count = 0
        self.status.showMessage(_("Streaming..."))

    def _stop_stream(self) -> None:
        if self.camera_thread is not None:
            logger.info("Stopping camera stream")
            self.camera_thread.stop()
            self.camera_thread = None
        if self.video_writer is not None:
            self._toggle_recording()  # cleanly closes the file
        self.camera_panel.set_streaming(False)
        self.video_view.show_message(_("Camera stopped"))
        self.status.showMessage(_("Idle"))

    def _on_error(self, kind: str, message: str) -> None:
        """No modal dialog: the image box itself says what happened, so the
        user can just pick another device or backend and press Start Stream again."""
        logger.error("Camera error (%s): %s", kind, message)
        self._stop_stream()
        headline = {
            ERR_NOT_DETECTED: _("Camera not detected"),
            ERR_LOST: _("Camera disconnected"),
        }.get(kind, _("Camera error"))
        self.video_view.show_message(f"{headline}\n\n{message}")
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
        self.video_view.show_frame(qimg, buffer=rgb)  # no copy: the view keeps `rgb` alive

        self.status.showMessage(_("Frame {count} | {fps:.1f} fps").format(count=self.frame_count, fps=fps))

    def _draw_overlays(self, frame: np.ndarray) -> np.ndarray:
        if self.display_panel.show_scale_bar:
            frame = draw_scale_bar(
                frame, self.display_panel.um_per_pixel_override, color=self.display_panel.scale_bar_color.bgr,
            )
        if self.capture_panel.burn_timestamp:
            ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
            cv2.putText(
                frame, ts, (10, frame.shape[0] - 12),
                cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 220, 90), 1, cv2.LINE_AA,
            )
        return frame

    def _toggle_recording_blink(self) -> None:
        self._recording_blink_on = not self._recording_blink_on

    # ----------------------------------------------------- Back to start --
    def _change_mode(self) -> None:
        """Open the start screen over the running window. Choosing a mode closes
        this window (releasing the camera and stage first); app.py then starts
        the chosen mode. Cancelling keeps everything running as it is."""
        language_before = current_language()
        chosen = ModeDialog.ask(default=self.mode)
        if chosen is None:
            if current_language() == language_before:
                return
            # The language changed but no mode was picked: rebuild this window
            # in the same mode so every text follows the new language.
            chosen = self.mode
        logger.info("Switching to %s mode (language: %s)", chosen.value, current_language())
        self.next_mode = chosen
        self.close()

    # -------------------------------------------------------------- Export --
    def _open_output_folder(self) -> None:
        if not open_in_file_manager(self._output_dir):
            self.status.showMessage(_("Could not open the folder {path}").format(path=self._output_dir))

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
        ts = datetime.now().strftime("%Y%m%d_%H%M%S_%f")[:-3]
        filename = self._output_dir / f"frame_{ts}.png"
        if not cv2.imwrite(str(filename), frame):
            logger.error("Could not write the snapshot %s", filename)
            self.status.showMessage(_("Could not save {filename}").format(filename=filename))
            return
        self.snapshot_count += 1
        logger.info("Saved snapshot %s", filename)
        self.status.showMessage(_("Saved {filename}  ({count} total)").format(filename=filename, count=self.snapshot_count))
        self._flash_snapshot()

    def _flash_snapshot(self) -> None:
        self.video_view.flash(SNAPSHOT_FLASH_MS)

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
            logger.info("Recording started: %s (%dx%d)", path, w, h)
            self.capture_panel.set_recording(True)
            self._recording_blink_on = True
            self.recording_blink_timer.start(RECORDING_BLINK_INTERVAL_MS)
            self.status.showMessage(_("Recording to {path}").format(path=path))
        else:
            self.video_writer.release()
            self.video_writer = None
            logger.info("Recording stopped")
            self.recording_blink_timer.stop()
            self._recording_blink_on = False
            self.capture_panel.set_recording(False)
            self.status.showMessage(_("Recording stopped"))

    # ------------------------------------------------------- Log and About --
    def _on_save_log_toggled(self, saving: bool) -> None:
        if not saving:
            self._log.stop_saving()
            self.log_bar.set_saving(False)
            self.status.showMessage(_("Log file deleted; the session is still being recorded"))
            return
        try:
            path = self._log.start_saving()
        except OSError as exc:
            logger.error("Could not open the log file: %s", exc)
            self.log_bar.set_saving(False)
            self.status.showMessage(_("Could not save the log: {error}").format(error=exc))
            return
        self.status.showMessage(_("Saving the log to {path}").format(path=path))

    def _open_log_folder(self) -> None:
        if not open_in_file_manager(self._log.folder):
            self.status.showMessage(_("Could not open the folder {path}").format(path=self._log.folder))

    def _show_log_viewer(self) -> None:
        if self._log_viewer is None:
            self._log_viewer = LogViewerDialog(self._log.history, self._log.read_full_log, self)
            self._log_viewer.open_folder_requested.connect(self._open_log_folder)
        self._log_viewer.show()
        self._log_viewer.raise_()
        self._log_viewer.activateWindow()

    def _show_about(self) -> None:
        AboutDialog(self).exec_()

    # ------------------------------------------------------------- Cleanup --
    def closeEvent(self, event) -> None:
        self._stop_stream()
        if hasattr(self, "recording_blink_timer"):
            self.recording_blink_timer.stop()
        if self.stage_module is not None:
            self.stage_module.shutdown()
        if self._log_viewer is not None:
            self._log_viewer.close()  # stops listening to the log before the window goes away
        event.accept()
