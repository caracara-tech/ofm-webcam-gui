"""Everything stage-related, bundled so MainWindow can simply not create it.

Owns the stage controller, the connection and movement threads, the position
poll timer, the StagePanel widget and the jog/autofocus handlers. In manual
mode this class is never instantiated, so there is no stage code to guard.

Connection policy (the same for every mode and every OS): the window always
opens normally and the stage connects in the background. If it cannot be
reached the status bar says "Stage not detected" with the reason (the full
text goes to the log), the stage controls stay off and the panel offers "Retry
connection". If it stops answering later (cable pulled, board reset) it
reports "Stage connection lost" the same way. Nothing blocks the start,
nothing is silently swallowed, and nothing is silently replaced by a simulation.
"""

from __future__ import annotations

import logging
from typing import Callable, Optional

import numpy as np
from PyQt5.QtCore import QObject, QTimer, pyqtSignal
from PyQt5.QtWidgets import QWidget

from core.autofocus import AutoFocusSettings
from core.config import SANGABOARD_MAX_STEPS_PER_SEC
from core.device_status import DeviceState, DeviceStatus
from core.i18n import _
from core.stage_motion import plan_jog
from core.types import Axis, Direction, StageMotionSettings
from hardware.abstract import StageController
from hardware.stage import SangaboardStageController
from .panels.stage_panel import StagePanel, direction_letter
from .threads.autofocus_thread import AutoFocusThread
from .threads.stage_connect_thread import StageConnectThread
from .threads.stage_thread import StageMovementThread

logger = logging.getLogger(__name__)

POSITION_POLL_INTERVAL_MS = 100
CONNECT_SHUTDOWN_WAIT_MS = 10_000  # how long closing the window waits for a connection attempt

# A connection attempt still running when its window closes must not be garbage
# collected mid-run (Qt aborts the process); parked here until it finishes.
_abandoned_threads: list[StageConnectThread] = []


_LOG_LABELS = {
    DeviceState.CONNECTING: "connecting",
    DeviceState.CONNECTED: "connected",
    DeviceState.NOT_DETECTED: "not detected",
    DeviceState.LOST: "connection lost",
}


def _not_detected_status(detail: str) -> DeviceStatus:
    return DeviceStatus(
        DeviceState.NOT_DETECTED,
        _("Stage not detected"),
        _("Check the USB cable and the board's power, then press Retry connection."),
        detail,
    )


def _lost_status(detail: str) -> DeviceStatus:
    return DeviceStatus(
        DeviceState.LOST,
        _("Stage connection lost"),
        _(
            "Stage controls have been disabled. Check the USB cable and the board's power, "
            "then press Retry connection. The position shown may no longer match the real stage position."
        ),
        detail,
    )


class StageModule(QObject):
    status_message = pyqtSignal(str)

    def __init__(
        self,
        stage: StageController,
        dialog_parent: QWidget,
        get_frame: Callable[[], Optional[np.ndarray]],
        get_frame_count: Callable[[], int],
        is_streaming: Callable[[], bool],
        stage_is_real: bool = True,
    ) -> None:
        super().__init__(dialog_parent)
        self.stage = stage
        self._dialog_parent = dialog_parent
        self._get_frame = get_frame
        self._get_frame_count = get_frame_count
        self._is_streaming = is_streaming
        self._stage_is_real = stage_is_real

        self.settings = StageMotionSettings()
        self._movement_busy = False
        self._status = DeviceStatus(DeviceState.CONNECTING, _("Connecting to the stage..."))
        self._autofocus_thread: Optional[AutoFocusThread] = None
        self._connect_thread: Optional[StageConnectThread] = None

        self.panel = StagePanel(self.settings)
        self.panel.jog_requested.connect(self._on_jog_requested)
        self.panel.settings_changed.connect(self._on_settings_changed)
        self.panel.autofocus_requested.connect(self._run_autofocus)
        self.panel.retry_requested.connect(self.retry_connection)
        self.panel.show_status(self._status)  # controls stay off until the stage answers

        self._thread = StageMovementThread()
        self._thread.movement_complete.connect(self._on_movement_complete)
        self._thread.movement_failed.connect(self._on_movement_failed)
        self._thread.start()

        self._timer = QTimer(self)
        self._timer.timeout.connect(self.refresh_position)
        self._timer.start(POSITION_POLL_INTERVAL_MS)

    # ------------------------------------------------------------ lifecycle --
    def start(self) -> None:
        """Begin connecting. Separate from __init__ so the caller can connect
        `status_message` first and not miss the first message."""
        self._begin_connect(reset=False)

    def shutdown(self) -> None:
        self._timer.stop()
        self._thread.stop()
        if self._autofocus_thread is not None:
            self._autofocus_thread.wait(2000)
        thread = self._connect_thread
        if thread is not None:
            thread.cancel()
            if not thread.wait(CONNECT_SHUTDOWN_WAIT_MS):
                _abandoned_threads.append(thread)
                thread.finished.connect(lambda t=thread: _abandoned_threads.remove(t))
            self._connect_thread = None
        self.stage.disconnect()

    @property
    def status(self) -> DeviceStatus:
        return self._status

    @property
    def _ready(self) -> bool:
        return self._status.is_ok

    def refresh_position(self) -> None:
        if self._ready and self.stage.is_connected():
            self.panel.update_position_display(self.stage.get_position_um())

    # ---------------------------------------------------------- connection --
    def retry_connection(self) -> None:
        """Try again after "not detected" or "connection lost"."""
        if self._connect_thread is not None or not self._status.can_retry:
            return
        if self._autofocus_thread is not None:
            self.status_message.emit(_("Wait for the auto-focus to stop, then retry."))
            return
        logger.info("Retrying the stage connection")
        self._begin_connect(reset=True)

    def _begin_connect(self, reset: bool) -> None:
        if self._connect_thread is not None:
            return
        self._set_status(DeviceStatus(DeviceState.CONNECTING, _("Connecting to the stage...")))
        thread = StageConnectThread(self.stage, reset=reset)
        thread.connected.connect(self._on_connected)
        thread.failed.connect(self._on_connect_failed)
        thread.finished.connect(thread.deleteLater)
        self._connect_thread = thread
        thread.start()

    def _finish_connect_thread(self) -> None:
        # The result signal is emitted from inside run(), so the QThread is
        # briefly still running: wait for it before dropping the reference.
        if self._connect_thread is not None:
            self._connect_thread.wait()
            self._connect_thread = None

    def _on_connected(self) -> None:
        self._finish_connect_thread()
        port = getattr(self.stage, "port", None)
        if not self._stage_is_real:
            headline = _("Simulated stage ready")
        else:
            headline = _("Stage connected ({port})").format(port=port) if port else _("Stage connected")
        self._movement_busy = False  # a move that was in flight when the stage was lost is gone
        self._set_status(DeviceStatus(DeviceState.CONNECTED, headline))
        self.panel.set_jog_enabled(True)
        self.refresh_position()

    def _on_connect_failed(self, detail: str) -> None:
        self._finish_connect_thread()
        self._set_status(_not_detected_status(detail))

    def _set_status(self, status: DeviceStatus) -> None:
        """Single place where the connection state changes: updates the panel,
        the status bar and the log together so they can never disagree."""
        self._status = status
        self.panel.show_status(status)
        self.status_message.emit(status.one_line())
        # The log line is framed in English whatever the interface language is;
        # only the underlying error (which may come from the system) can differ.
        failed = status.state in (DeviceState.NOT_DETECTED, DeviceState.LOST)
        logger.log(
            logging.ERROR if failed else logging.INFO,
            "Stage %s%s", _LOG_LABELS[status.state], f": {' '.join(status.detail.split())}" if status.detail else "",
        )

    # ---------------------------------------------------------------- jogs --
    def _on_settings_changed(self, settings: StageMotionSettings) -> None:
        self.settings = settings

    def _on_jog_requested(self, direction: Direction) -> None:
        if self._movement_busy or not self._ready:
            return  # a jog or autofocus sweep is already in flight (or the stage is not available)
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
        While the stage is not connected the whole panel is disabled anyway;
        reconnecting re-enables the buttons (see _on_connected)."""
        self._movement_busy = busy
        if self._ready:
            self.panel.set_jog_enabled(not busy)

    # ----------------------------------------------------------- autofocus --
    def _run_autofocus(self) -> None:
        if self._movement_busy or not self._ready:
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
        if not self._ready:
            return  # one report per failure, even if several signals arrive
        self._set_status(_lost_status(detail))
