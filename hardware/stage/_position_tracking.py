"""
Small internal helper shared by all concrete StageController implementations.

Every backend (Arduino, Sangaboard, Mock) tracks its own logical (x, y, z) in
steps and needs to turn a `Direction` + step count into a position delta the
same way. Rather than duplicate that arithmetic three times, it lives here.
"""

from __future__ import annotations

from core.types import Direction, Position


class PositionTrackingMixin:
    """Expects the including class to set self._x/_y/_z ints in __init__."""

    _x: int
    _y: int
    _z: int

    def get_position(self) -> Position:
        return Position(self._x, self._y, self._z)

    def set_position(self, x: float = 0, y: float = 0, z: float = 0, relative_move_to_target: bool = False) -> None:
        if relative_move_to_target:
            dx_steps = int(x) - self._x
            dy_steps = int(y) - self._y
            dz_steps = int(z) - self._z

            if dx_steps:
                self.move_steps(Direction.RIGHT if dx_steps > 0 else Direction.LEFT, abs(dx_steps), 0)  # type: ignore[attr-defined]
            if dy_steps:
                self.move_steps(Direction.UP if dy_steps > 0 else Direction.DOWN, abs(dy_steps), 0)  # type: ignore[attr-defined]
            if dz_steps:
                self.move_steps(Direction.FORWARD if dz_steps > 0 else Direction.BACKWARD, abs(dz_steps), 0)  # type: ignore[attr-defined]
        else:
            self._x, self._y, self._z = int(x), int(y), int(z)

    def _apply_step_delta(self, direction: Direction, actual_steps: int) -> None:
        dx = dy = dz = 0
        if direction.axis.value == "x":
            dx = direction.sign * actual_steps
        elif direction.axis.value == "y":
            dy = direction.sign * actual_steps
        else:
            dz = direction.sign * actual_steps
        self._x += dx
        self._y += dy
        self._z += dz
