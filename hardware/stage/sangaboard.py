"""Concrete StageController for Sangaboard-based stages."""

from __future__ import annotations

import logging
import time
from typing import Callable, Optional

from core.config import SANGABOARD_MAX_STEPS_PER_SEC, default_stage_port
from core.types import AxisCalibration, Direction
from hardware.abstract import StageController
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
        self.port = port or default_stage_port()
        self.timeout = timeout
        self.sb = None
        self._connected = False
        self._x = self._y = self._z = 0

    def connect(self) -> None:
        if Sangaboard is None:
            logger.warning("Sangaboard library not available.")
            return
        try:
            self.sb = Sangaboard(port=self.port, timeout=self.timeout)
            self._connected = True
            logger.info("Sangaboard connected on %s", self.port)
        except Exception as e:
            logger.warning("Could not connect to Sangaboard at %s: %s", self.port, e)
            self._connected = False
            self.sb = None

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
            logger.warning("Sangaboard not connected")
            return

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
