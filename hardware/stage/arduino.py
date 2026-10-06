"""Concrete StageController for the Arduino-based stage."""

from __future__ import annotations

import logging
import time
from typing import Callable, Optional

import serial

from core.config import default_arduino_port
from core.types import AxisCalibration, Direction
from hardware.abstract import StageController
from ._position_tracking import PositionTrackingMixin

logger = logging.getLogger(__name__)

# User-measured defaults: 244nm in y, 610nm in x, 305.5nm in z
ARDUINO_CALIBRATION = AxisCalibration(x_nm_per_step=610.0, y_nm_per_step=244.0, z_nm_per_step=305.5)


class ArduinoStageController(PositionTrackingMixin, StageController):
    """Stage controller for the Arduino-based setup, talking raw single-char
    move commands ('L','R','U','D','W','S') over a serial connection."""

    def __init__(self, port: Optional[str] = None, baudrate: int = 9600, timeout: float = 1):
        super().__init__(calibration=ARDUINO_CALIBRATION)
        self.port = port or default_arduino_port()
        self.baudrate = baudrate
        self.timeout = timeout
        self.connection: Optional[serial.Serial] = None
        self._connected = False
        self._x = self._y = self._z = 0

    def connect(self) -> None:
        try:
            self.connection = serial.Serial(self.port, self.baudrate, timeout=self.timeout)
            time.sleep(2)  # Wait for Arduino reset
            self._connected = True
            logger.info("Stage connected on %s", self.port)
        except Exception as e:
            logger.warning("Could not connect to Stage at %s: %s", self.port, e)
            self._connected = False
            self.connection = None

    def disconnect(self) -> None:
        if self.connection and self.connection.is_open:
            self.connection.close()
        self._connected = False
        self.connection = None

    def is_connected(self) -> bool:
        return bool(self._connected and self.connection and self.connection.is_open)

    def send_command(self, cmd: str) -> None:
        if not self.is_connected():
            logger.warning("Stage not connected (send_command)")
            return
        try:
            self.connection.write(cmd.encode())  # type: ignore[union-attr]
            self.connection.flush()  # type: ignore[union-attr]
        except Exception as e:
            logger.error("Error sending command '%s': %s", cmd, e)

    def _move_steps_raw(
        self,
        direction: Direction,
        steps: int,
        delay_per_step_s: float,
        callback: Optional[Callable[[], None]],
    ) -> None:
        if not self.is_connected():
            logger.warning("Stage not connected (move_steps)")
            return

        self._stop_requested = False
        actual_steps = 0
        for _ in range(steps):
            if self._stop_requested:
                logger.info("Stage movement aborted.")
                break
            try:
                self.connection.write(direction.value.encode())  # type: ignore[union-attr]
                self.connection.flush()  # type: ignore[union-attr]
                time.sleep(delay_per_step_s)
                actual_steps += 1
                if callback:
                    callback()
            except Exception as e:
                logger.error("Error during move_steps: %s", e)
                break

        self._apply_step_delta(direction, actual_steps)

    def set_step_delay(self, delay_us: int) -> bool:
        logger.info("Speed control (step delay) not supported on Arduino controller.")
        return False

    def stop(self) -> bool:
        self._stop_requested = True
        return True
