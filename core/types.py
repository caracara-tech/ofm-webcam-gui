"""
Shared, strongly-typed data structures used across the hardware and UI layers.

Keeping these in one place means hardware code and UI code agree on the
shape of a "position", an "axis", a "resolution", etc. without either side
importing from the other.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import NamedTuple, Optional


class Axis(str, Enum):
    """A stage axis. str-based so it prints/serializes cleanly."""

    X = "x"
    Y = "y"
    Z = "z"


class Direction(str, Enum):
    """A single-step motion command understood by all stage controllers."""

    LEFT = "L"
    RIGHT = "R"
    UP = "U"
    DOWN = "D"
    FORWARD = "W"  # +Z
    BACKWARD = "S"  # -Z

    @property
    def axis(self) -> Axis:
        return {
            Direction.LEFT: Axis.X,
            Direction.RIGHT: Axis.X,
            Direction.UP: Axis.Y,
            Direction.DOWN: Axis.Y,
            Direction.FORWARD: Axis.Z,
            Direction.BACKWARD: Axis.Z,
        }[self]

    @property
    def sign(self) -> int:
        return {
            Direction.LEFT: -1,
            Direction.RIGHT: 1,
            Direction.UP: 1,
            Direction.DOWN: -1,
            Direction.FORWARD: 1,
            Direction.BACKWARD: -1,
        }[self]


class Position(NamedTuple):
    """A 3-axis position. Unit is implied by the accessor used to obtain it
    (steps, nm, or um) — never mix units without converting explicitly."""

    x: float
    y: float
    z: float


@dataclass(frozen=True)
class AxisCalibration:
    """Nanometres-per-step calibration factors for a stage."""

    x_nm_per_step: float
    y_nm_per_step: float
    z_nm_per_step: float

    def nm_per_step(self, axis: Axis) -> float:
        return {
            Axis.X: self.x_nm_per_step,
            Axis.Y: self.y_nm_per_step,
            Axis.Z: self.z_nm_per_step,
        }[axis]


@dataclass(frozen=True)
class Resolution:
    label: str
    width: int
    height: int


@dataclass(frozen=True)
class CameraBackend:
    label: str
    cv2_flag: int  # a cv2.CAP_* constant


@dataclass
class StageMotionSettings:
    """Mutable UI-driven settings for manual jogging."""

    xy_step_um: float = 10.0
    z_step_um: float = 1.0
    speed_um_per_s: float = 100.0
    autofocus_after_xy_jog: bool = False
