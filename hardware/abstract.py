"""
Abstract base classes for hardware controllers.

`StageController` defines the full public contract used by the UI layer.
Concrete subclasses only need to implement the small "raw" primitives
(`connect`, `_move_steps_raw`, `get_position`, ...); the higher-level
convenience methods (`move_steps`, unit conversions, position-in-nm/um)
are implemented once, here, so behaviour can't drift between backends.
"""

from __future__ import annotations

import abc
from typing import Callable, Optional

from core.types import Axis, AxisCalibration, Direction, Position


class StageController(abc.ABC):
    """Abstract base class for stage controllers."""

    def __init__(self, calibration: AxisCalibration, min_step_delay_us: int = 0) -> None:
        self.calibration = calibration
        self.min_step_delay_us = min_step_delay_us
        self._stop_requested = False

    # -- Unit conversion -------------------------------------------------
    def get_position_nm(self) -> Position:
        steps = self.get_position()
        return Position(
            steps.x * self.calibration.nm_per_step(Axis.X),
            steps.y * self.calibration.nm_per_step(Axis.Y),
            steps.z * self.calibration.nm_per_step(Axis.Z),
        )

    def get_position_um(self) -> Position:
        nm = self.get_position_nm()
        return Position(nm.x / 1000.0, nm.y / 1000.0, nm.z / 1000.0)

    def steps_to_nm(self, steps: float, axis: Axis) -> float:
        return steps * self.calibration.nm_per_step(axis)

    def nm_to_steps(self, nm: float, axis: Axis) -> int:
        scale = self.calibration.nm_per_step(axis)
        return int(round(nm / scale)) if scale else 0

    def um_to_steps(self, um: float, axis: Axis) -> int:
        return self.nm_to_steps(um * 1000.0, axis)

    # -- High-level motion -------------------------------------------------
    def move_steps(
        self,
        direction: Direction,
        steps: int,
        delay_per_step_s: float,
        callback: Optional[Callable[[], None]] = None,
    ) -> None:
        """Move `steps` steps in `direction`, honouring the controller's
        minimum step delay. This is the method UI/thread code should call;
        subclasses implement the hardware-specific `_move_steps_raw`."""
        min_delay_s = self.min_step_delay_us / 1_000_000.0
        delay_per_step_s = max(delay_per_step_s, min_delay_s)
        self._move_steps_raw(direction, max(0, int(steps)), delay_per_step_s, callback)

    # -- Abstract primitives, implemented per backend ----------------------
    @abc.abstractmethod
    def connect(self) -> None: ...

    @abc.abstractmethod
    def disconnect(self) -> None: ...

    @abc.abstractmethod
    def is_connected(self) -> bool: ...

    @abc.abstractmethod
    def send_command(self, cmd: str) -> None: ...

    @abc.abstractmethod
    def _move_steps_raw(
        self,
        direction: Direction,
        steps: int,
        delay_per_step_s: float,
        callback: Optional[Callable[[], None]],
    ) -> None: ...

    @abc.abstractmethod
    def stop(self) -> bool: ...

    @abc.abstractmethod
    def set_step_delay(self, delay_us: int) -> bool: ...

    @abc.abstractmethod
    def get_position(self) -> Position:
        """Current (x, y, z) in steps."""

    @abc.abstractmethod
    def set_position(self, x: float = 0, y: float = 0, z: float = 0, relative_move_to_target: bool = False) -> None:
        """Set the logical position. If `relative_move_to_target`, physically
        move the stage by the delta between current and target; otherwise
        just overwrite the internal position register (if supported)."""


class SensorController(abc.ABC):
    """Abstract base class for sensor controllers (camera, power meter, etc.)."""

    @abc.abstractmethod
    def connect(self) -> None: ...

    @abc.abstractmethod
    def disconnect(self) -> None: ...

    @abc.abstractmethod
    def get_measurement(self): ...

    @abc.abstractmethod
    def get_averaged_measurement(self, n_avg: int = 1, timeout_scale: float = 1.0): ...

    @abc.abstractmethod
    def get_device_info(self): ...


class CameraController(SensorController):
    """Abstract base class for camera controllers (SDK-driven, e.g. scientific cameras;
    distinct from the OpenCV `cv2.VideoCapture`-based webcam path used elsewhere)."""

    @abc.abstractmethod
    def arm(self, buffer_count: int = 2): ...

    @abc.abstractmethod
    def set_exposure(self, exposure_ms: float): ...

    @abc.abstractmethod
    def set_gain(self, gain_db: float): ...

    @abc.abstractmethod
    def start_acquisition(self): ...

    @abc.abstractmethod
    def stop_acquisition(self): ...

    @abc.abstractmethod
    def get_frame(self):
        """Returns a processed frame (2D numpy array) or None."""

    @abc.abstractmethod
    def get_averaged_frame(self, n_avg: int = 1, timeout_scale: float = 1.0): ...

    @abc.abstractmethod
    def set_roi(self, x: int, y: int, width: int, height: int): ...

    @abc.abstractmethod
    def reset_roi(self): ...

    @abc.abstractmethod
    def get_roi(self): ...
