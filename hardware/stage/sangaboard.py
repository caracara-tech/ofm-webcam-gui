"""Concrete StageController for Sangaboard-based stages."""

from __future__ import annotations

import logging
import time
from typing import Callable, Optional

from core.config import SANGABOARD_MAX_STEPS_PER_SEC, default_stage_port
from core.platform_info import CURRENT_PLATFORM, Platform
from core.types import AxisCalibration, Direction
from hardware.abstract import StageController
from hardware.errors import StageCommunicationError
from ._position_tracking import PositionTrackingMixin

logger = logging.getLogger(__name__)

try:
    from sangaboard import Sangaboard
except ImportError:
    Sangaboard = None  # type: ignore[assignment,misc]
    logger.info("Sangaboard module not found. SangaboardStageController will not be available.")

# User-measured default: Sangaboard step size 12.2nm on all axes
SANGABOARD_CALIBRATION = AxisCalibration(x_nm_per_step=12.2, y_nm_per_step=12.2, z_nm_per_step=12.2)
SANGABOARD_MIN_STEP_DELAY_US = 1000
CHUNK_SIZE_STEPS = 1000


class SangaboardStageController(PositionTrackingMixin, StageController):
    """Stage controller for a Sangaboard microscope stage."""

    def __init__(self, port: Optional[str] = None, timeout: float = 2):
        super().__init__(calibration=SANGABOARD_CALIBRATION, min_step_delay_us=SANGABOARD_MIN_STEP_DELAY_US)
        self._explicit_port = port is not None
        self.port = port or default_stage_port()
        self.timeout = timeout
        self.sb = None
        self._connected = False
        self._x = self._y = self._z = 0

    def connect(self) -> None:
        """Open the Sangaboard, or raise StageCommunicationError.

        With no explicit port, the platform's default port is tried first;
        if that fails, the `sangaboard` library scans every serial port
        (port=None) so a different COM/tty number doesn't matter.
        """
        if Sangaboard is None:
            raise StageCommunicationError(
                "The 'sangaboard' Python package is not installed (pip install sangaboard)."
            )

        candidates = [self.port] if self._explicit_port else [self.port, None]
        errors: list[str] = []
        for candidate in candidates:
            try:
                self.sb = Sangaboard(port=candidate, timeout=self.timeout)
            except Exception as e:
                logger.warning("Could not connect to Sangaboard (port=%s): %s", candidate or "auto-scan", e)
                errors.append(str(e))
                self.sb = None
                continue
            self._connected = True
            used = getattr(getattr(self.sb, "_ser", None), "port", None) or candidate or self.port
            self.port = used
            logger.info("Sangaboard connected on %s", used)
            return

        self._connected = False
        raise StageCommunicationError(_explain_connection_failure(self.port, self._explicit_port, errors, scanned=len(candidates) > 1))

    def disconnect(self) -> None:
        if self.sb:
            try:
                self.sb.close()
            except Exception:
                pass
        self._connected = False
        self.sb = None

    def is_connected(self) -> bool:
        return self._connected and self.sb is not None

    def send_command(self, cmd: str) -> None:
        try:
            direction = Direction(cmd.upper())
        except ValueError:
            logger.warning("SangaboardStageController: Unknown/unsupported command '%s'", cmd)
            return
        self.move_steps(direction, 1, 0)

    def _move_steps_raw(
        self,
        direction: Direction,
        steps: int,
        delay_per_step_s: float,
        callback: Optional[Callable[[], None]],
    ) -> None:
        if not self.is_connected():
            raise StageCommunicationError("The stage is not connected.")

        self._stop_requested = False
        dx = dy = dz = 0
        if direction.axis.value == "x":
            dx = direction.sign
        elif direction.axis.value == "y":
            dy = direction.sign
        else:
            dz = direction.sign

        if steps == 0:
            return

        logger.debug("[Sangaboard] Move requesting: %s (total steps=%d)", (dx * steps, dy * steps, dz * steps), steps)

        steps_remaining = steps
        actual_steps = 0
        try:
            while steps_remaining > 0:
                if self._stop_requested:
                    logger.info("[Sangaboard] Move aborted by user.")
                    break
                chunk = min(steps_remaining, CHUNK_SIZE_STEPS)
                self.sb.move_rel([dx * chunk, dy * chunk, dz * chunk])
                actual_steps += chunk
                steps_remaining -= chunk

            logger.debug("[Sangaboard] Move sequence complete.")
            if callback:
                callback()
        except Exception as e:
            logger.error("Error during Sangaboard move: %s", e)
            self._connected = False
            raise StageCommunicationError(
                f"Lost communication with the stage during a move ({e}). "
                "Check the USB cable and the board's power."
            ) from e
        finally:
            self._apply_step_delta(direction, actual_steps)

    def set_step_delay(self, delay_us: int) -> bool:
        if not self.is_connected():
            logger.warning("Sangaboard not connected")
            return False
        try:
            delay_us = max(delay_us, self.min_step_delay_us)
            logger.debug("[Sangaboard] Setting step_delay to %d us", delay_us)
            self.sb.step_time = int(delay_us)
            return True
        except Exception as e:
            logger.error("Error setting step delay on Sangaboard: %s", e)
            self._connected = False
            return False

    def stop(self) -> bool:
        self._stop_requested = True
        if self.is_connected() and self.sb:
            try:
                if hasattr(self.sb, "stop"):
                    self.sb.stop()
                else:
                    self.sb.move_rel([0, 0, 0])
                logger.info("Sangaboard movement stopped.")
                return True
            except Exception as e:
                logger.error("Error stopping Sangaboard: %s", e)
                return False
        return True


def _explain_connection_failure(port: str, explicit: bool, errors: list[str], scanned: bool) -> str:
    """Build a user-facing explanation, distinguishing the common causes."""
    try:
        from serial.tools import list_ports
        visible = [f"{p.device} ({p.description})" for p in list_ports.comports()]
    except Exception:
        visible = []

    # The first error is the one for the configured/default port; the generic
    # "no valid port" text from the automatic scan is not useful to the user.
    detail = next((e for e in errors if e), "no response")
    lines = [f"Could not connect to the Sangaboard on {port}.", f"Reason: {detail}"]
    if scanned:
        lines.append("An automatic scan of the other serial ports did not find a Sangaboard either.")

    lowered = detail.lower()
    if "permission" in lowered or "access is denied" in lowered:
        lines.append(
            "The port exists but could not be opened. Another program may be using it"
            + (
                ", or your user is not in the 'dialout' group "
                "(sudo usermod -aG dialout $USER, then log out and back in)."
                if CURRENT_PLATFORM == Platform.LINUX else "."
            )
        )
    elif not visible:
        lines.append("No serial ports were found at all. Is the board plugged in and powered?")
    else:
        lines.append("Serial ports visible to this computer: " + ", ".join(visible))
    return "\n".join(lines)
