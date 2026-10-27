"""QThread that connects (or reconnects) a stage without blocking the window.

Opening a serial port can take seconds (the Sangaboard library scans every
port when the default one fails), so it must not run on the GUI thread.
"""

from __future__ import annotations

import logging

from PyQt5.QtCore import QThread, pyqtSignal

from core.i18n import _
from hardware.abstract import StageController
from hardware.errors import StageCommunicationError

logger = logging.getLogger(__name__)


class StageConnectThread(QThread):
    """Emits exactly one of `connected()` or `failed(message)`, then ends.

    `failed` carries the user-readable explanation from the hardware layer.
    """

    connected = pyqtSignal()
    failed = pyqtSignal(str)

    def __init__(self, stage: StageController, reset: bool = False) -> None:
        """`reset=True` (a retry) closes whatever is left of the previous
        connection first, so a half-dead port from a lost stage is not reused."""
        super().__init__()
        self._stage = stage
        self._reset = reset
        self._cancelled = False

    def cancel(self) -> None:
        """The window is closing: release the stage if the connection succeeds anyway."""
        self._cancelled = True

    def run(self) -> None:
        try:
            if self._reset:
                self._stage.disconnect()
            self._stage.connect()
        except StageCommunicationError as exc:
            self.failed.emit(str(exc))
            return
        except Exception as exc:  # a backend bug must still end as a visible "not detected"
            logger.exception("Unexpected error while connecting to the stage")
            self.failed.emit(_("Unexpected error while connecting to the stage: {error}").format(error=exc))
            return

        if not self._stage.is_connected():
            # Some backends report failure by returning instead of raising.
            self.failed.emit(_("The stage did not respond."))
        elif self._cancelled:
            self._stage.disconnect()
        else:
            self.connected.emit()
