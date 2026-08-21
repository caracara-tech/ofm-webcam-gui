"""Mock StageController for simulation/testing without physical hardware."""

from __future__ import annotations

import logging
import time
from typing import Callable, Optional

from core.config import SIMULATION_SPEED_MULTIPLIER
from core.types import AxisCalibration, Direction
from hardware.abstract import StageController
from ._position_tracking import PositionTrackingMixin

logger = logging.getLogger(__name__)

# Reuse Sangaboard calibration for a realistic simulation.
MOCK_CALIBRATION = AxisCalibration(x_nm_per_step=12.2, y_nm_per_step=12.2, z_nm_per_step=12.2)


class MockStageController(PositionTrackingMixin, StageController):
    """Simulates all stage operations without requiring physical hardware."""

    def __init__(self, simulation_speed_multiplier: float = SIMULATION_SPEED_MULTIPLIER):
        super().__init__(calibration=MOCK_CALIBRATION)
        self._connected = True  # Always "connected"
        self._x = self._y = self._z = 0
        self.simulation_speed_multiplier = simulation_speed_multiplier
        logger.info("[MockStageController] Initialized (simulation mode)")

    def connect(self) -> None:
        self._connected = True
        logger.info("[MockStageController] Connected (simulation)")

    def disconnect(self) -> None:
        self._connected = False
        logger.info("[MockStageController] Disconnected (simulation)")

    def is_connected(self) -> bool:
        return self._connected

    def send_command(self, cmd: str) -> None:
        try:
            direction = Direction(cmd.upper())
        except ValueError:
            logger.warning("[MockStageController] Unknown command '%s'", cmd)
            return
        self.move_steps(direction, 1, 0)

    def _move_steps_raw(
        self,
        direction: Direction,
        steps: int,
        delay_per_step_s: float,
        callback: Optional[Callable[[], None]],
    ) -> None:
        self._stop_requested = False
        sim_delay = delay_per_step_s / self.simulation_speed_multiplier if delay_per_step_s > 0 else 0.001

        actual_steps = 0
        for _ in range(steps):
            if self._stop_requested:
                logger.info("[MockStageController] Movement aborted.")
                break
            time.sleep(sim_delay)
            actual_steps += 1
            if callback:
                callback()

        self._apply_step_delta(direction, actual_steps)
        pos_um = self.get_position_um()
        logger.debug(
            "[MockStageController] Moved %s %d steps -> Position: (%.2f, %.2f, %.2f) um",
            direction.value, actual_steps, pos_um.x, pos_um.y, pos_um.z,
        )

    def set_step_delay(self, delay_us: int) -> bool:
        logger.debug("[MockStageController] Step delay set to %d us (simulation)", delay_us)
        return True

    def stop(self) -> bool:
        self._stop_requested = True
        logger.info("[MockStageController] Movement stopped (simulation)")
        return True
