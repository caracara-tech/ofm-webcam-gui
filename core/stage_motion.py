"""
Pure functions for translating a UI jog request (direction + step/speed
settings) into hardware-agnostic (steps, delay_per_step_s) values.

Kept free of PyQt and hardware-backend imports so it's trivially unit
testable and reusable outside the GUI.
"""

from __future__ import annotations

from dataclasses import dataclass

from .types import AxisCalibration, Direction, StageMotionSettings

MIN_SPEED_UM_S = 0.1


@dataclass(frozen=True)
class JogPlan:
    steps: int
    delay_per_step_s: float
    distance_um: float


def plan_jog(
    direction: Direction,
    settings: StageMotionSettings,
    calibration: AxisCalibration,
    *,
    steps_per_sec_limit: float | None = None,
) -> JogPlan:
    """Compute how many steps to take and the delay between them for a
    single manual jog in `direction`, given the current UI settings."""
    step_um = settings.xy_step_um if direction.axis.value in ("x", "y") else settings.z_step_um
    distance_um = direction.sign * step_um

    scale_nm = calibration.nm_per_step(direction.axis)
    steps = int(round(abs(distance_um) * 1000.0 / scale_nm)) if scale_nm else 0

    speed_um_s = max(settings.speed_um_per_s, MIN_SPEED_UM_S)
    steps_per_sec = (speed_um_s * 1000.0) / scale_nm if scale_nm else 0.0
    if steps_per_sec_limit is not None:
        steps_per_sec = min(steps_per_sec, steps_per_sec_limit)

    delay_s = 1.0 / steps_per_sec if steps_per_sec > 0 else 0.1

    return JogPlan(steps=steps, delay_per_step_s=delay_s, distance_um=distance_um)
