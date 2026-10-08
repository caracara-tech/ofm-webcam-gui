"""Everything stage-related, bundled so MainWindow can simply not create it.

Owns the stage controller, the movement thread, the position poll timer,
the StagePanel widget and the jog/autofocus handlers. In camera-only mode
this class is never instantiated, so there is no stage code to guard.

Failure policy: if the stage stops answering (cable pulled, board reset),
an explicit error dialog is shown once, the panel is disabled and its title
says so. Nothing is silently swallowed or silently replaced by a simulation.
"""

from __future__ import annotations

import logging
from typing import Callable, Optional

import numpy as np
from PyQt5.QtCore import QObject, QTimer, pyqtSignal
from PyQt5.QtWidgets import QMessageBox, QWidget

from core.autofocus import AutoFocusSettings
from core.config import SANGABOARD_MAX_STEPS_PER_SEC
from core.i18n import _
from core.stage_motion import plan_jog
from core.types import Axis, Direction, StageMotionSettings
from hardware.abstract import StageController
from hardware.stage import SangaboardStageController
from .panels.stage_panel import StagePanel, direction_letter
from .threads.autofocus_thread import AutoFocusThread
from .threads.stage_thread import StageMovementThread

logger = logging.getLogger(__name__)

POSITION_POLL_INTERVAL_MS = 100


class StageModule(QObject):
    status_message = pyqtSignal(str)

    def __init__(
        self,
        stage: StageController,
        dialog_parent: QWidget,
        get_frame: Callable[[], Optional[np.ndarray]],
        get_frame_count: Callable[[], int],
        is_streaming: Callable[[], bool],
    ) -> None:
        super().__init__(dialog_parent)
        self.stage = stage
        self._dialog_parent = dialog_parent
        self._get_frame = get_frame
        self._get_frame_count = get_frame_count
        self._is_streaming = is_streaming

        self.settings = StageMotionSettings()
        self._movement_busy = False
        self._connection_lost = False
        self._autofocus_thread: Optional[AutoFocusThread] = None

        self.panel = StagePanel(self.settings)
        self.panel.jog_requested.connect(self._on_jog_requested)
        self.panel.settings_changed.connect(self._on_settings_changed)
        self.panel.autofocus_requested.connect(self._run_autofocus)

        self._thread = StageMovementThread()
        self._thread.movement_complete.connect(self._on_movement_complete)
        self._thread.movement_failed.connect(self._on_movement_failed)
        self._thread.start()

        self._timer = QTimer(self)
        self._timer.timeout.connect(self.refresh_position)
        self._timer.start(POSITION_POLL_INTERVAL_MS)
        self.refresh_position()

    # ------------------------------------------------------------ lifecycle --
    def shutdown(self) -> None:
        self._timer.stop()
        self._thread.stop()
        if self._autofocus_thread is not None:
            self._autofocus_thread.wait(2000)
        self.stage.disconnect()

    def refresh_position(self) -> None:
        if self.stage.is_connected():
            self.panel.update_position_display(self.stage.get_position_um())

    # ---------------------------------------------------------------- jogs --
    def _on_settings_changed(self, settings: StageMotionSettings) -> None:
        self.settings = settings

    def _on_jog_requested(self, direction: Direction) -> None:
        if self._movement_busy or self._connection_lost:
            return  # a jog or autofocus sweep is already in flight (or the stage is gone)
        if not self.stage.is_connected():
            self._handle_stage_failure(_("The stage is not connected."))
            return

        steps_per_sec_limit = (
            SANGABOARD_MAX_STEPS_PER_SEC if isinstance(self.stage, SangaboardStageController) else None
        )
        plan = plan_jog(
            direction, self.settings, self.stage.calibration,
            steps_per_sec_limit=steps_per_sec_limit,
        )
        if plan.steps <= 0:
            return

        if hasattr(self.stage, "set_step_delay"):
            if self.stage.set_step_delay(int(plan.delay_per_step_s * 1e6)) is False:
                self._handle_stage_failure(_("The stage did not accept the speed setting (no response)."))
                return

        self._set_movement_busy(True)
        self._thread.add_movement(
            self.stage, direction, plan.steps, plan.delay_per_step_s,
            _("Moved {direction} {distance:.1f} \u00b5m").format(
                direction=direction_letter(direction), distance=plan.distance_um,
            ),
        )

    def _on_movement_complete(self, message: str, direction: Direction) -> None:
        self.status_message.emit(message)
        self.refresh_position()
        self._set_movement_busy(False)

        if direction.axis != Axis.Z and self.settings.autofocus_after_xy_jog:
            self._run_autofocus()

    def _on_movement_failed(self, message: str, _direction: Direction) -> None:
        self.refresh_position()
        self._handle_stage_failure(message)

    def _set_movement_busy(self, busy: bool) -> None:
        """Disables the jog/autofocus buttons for the duration of a move so
        a second movement can't be queued on top of one that's in flight.
        Once the connection is lost the buttons stay disabled for good."""
        self._movement_busy = busy
        if not self._connection_lost:
            self.panel.set_jog_enabled(not busy)

    # ----------------------------------------------------------- autofocus --
    def _run_autofocus(self) -> None:
        if self._movement_busy or self._connection_lost:
            return
        if not self.stage.is_connected():
            self._handle_stage_failure(_("The stage is not connected."))
            return
        if not self._is_streaming() or self._get_frame() is None:
            self.status_message.emit(_("Start the camera stream before running autofocus."))
            return

        self._set_movement_busy(True)
        self.status_message.emit(_("Running auto-focus..."))

        self._autofocus_thread = AutoFocusThread(
            self.stage, self._get_frame, AutoFocusSettings(),
            frame_id_getter=self._get_frame_count,
        )
        self._autofocus_thread.progress.connect(self._on_autofocus_progress)
        self._autofocus_thread.stage_failed.connect(self._handle_stage_failure)
        self._autofocus_thread.finished_focus.connect(self._on_autofocus_finished)
        # Let Qt tear the QThread down only once it has actually finished
        # running (finished() fires after run() has fully returned), rather
        # than us dropping the last Python reference to it ourselves.
        self._autofocus_thread.finished.connect(self._autofocus_thread.deleteLater)
        self._autofocus_thread.start()

    def _on_autofocus_progress(self, step: int, total: int) -> None:
        self.status_message.emit(_("Auto-focus: sampling position {step}/{total}...").format(step=step, total=total))

    def _on_autofocus_finished(self, message: str) -> None:
        self.status_message.emit(message)
        self.refresh_position()
        self._set_movement_busy(False)
        # finished_focus is emitted from inside run(), so the QThread is
        # briefly still "running" from Qt's point of view. Dropping the only
        # Python reference in that window destroys a running QThread (fatal
        # abort), so wait for it to wind down first.
        if self._autofocus_thread is not None:
            self._autofocus_thread.wait()
        self._autofocus_thread = None

    # ------------------------------------------------------------- failure --
    def _handle_stage_failure(self, detail: str) -> None:
        if self._connection_lost:
            return  # one dialog per failure, even if several signals arrive
        self._connection_lost = True
        logger.error("Stage communication failure: %s", detail)
        self.panel.set_enabled_all(False)
        self.panel.setTitle(_("Stage Control \u2014 CONNECTION LOST"))
        self.status_message.emit(_("Stage connection lost"))
        QMessageBox.critical(
            self._dialog_parent, _("Stage communication error"),
            _(
                "{detail}\n\n"
                "Stage controls have been disabled. Check the USB cable and the "
                "board's power, then restart the application to reconnect.\n\n"
                "The position shown may no longer match the real stage position."
            ).format(detail=detail),
        )
