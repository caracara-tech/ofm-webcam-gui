"""
Which long-running activities are in progress, and how each one is shown on
the preview (a coloured badge, see `core/overlays.py`).

Pure state, no Qt and no hardware: the window tells the tracker when an
activity starts, changes or ends, and asks it for the badges to draw. A new
activity (homing, calibration...) needs one `Activity` member and nothing else:
the drawing, the stacking and the blinking are shared.

Several activities can run at once (recording while autofocusing is normal).
They are listed in the fixed order of the `Activity` enum, so their rows keep
their place and never jump when another one starts or stops.
"""

from __future__ import annotations

from enum import Enum
from typing import Dict, List

from .overlays import BGR, Badge


class Activity(Enum):
    """(on-screen label, colour). Declaration order = top-to-bottom order."""

    RECORDING = ("REC", (0, 0, 255))          # red
    AUTOFOCUS = ("AUTOFOCUS", (0, 165, 255))  # amber

    @property
    def label(self) -> str:
        return self.value[0]

    @property
    def color(self) -> BGR:
        return self.value[1]


class ActivityTracker:
    """The set of running activities, an optional short detail text for each
    (e.g. "fine 5/9") and the shared blink phase of the badges' dots."""

    def __init__(self) -> None:
        self._details: Dict[Activity, str] = {}
        self._blink_on = True

    def start(self, activity: Activity, detail: str = "") -> None:
        if not self._details:
            self._blink_on = True  # the first badge appears with its dot lit, not mid-blink
        self._details[activity] = detail

    def update(self, activity: Activity, detail: str) -> None:
        """Change the detail text of a running activity (ignored if it is not running)."""
        if activity in self._details:
            self._details[activity] = detail

    def stop(self, activity: Activity) -> None:
        self._details.pop(activity, None)

    def is_active(self, activity: Activity) -> bool:
        return activity in self._details

    @property
    def any_active(self) -> bool:
        return bool(self._details)

    def toggle_blink(self) -> None:
        self._blink_on = not self._blink_on

    @property
    def blink_on(self) -> bool:
        return self._blink_on

    def badges(self) -> List[Badge]:
        """The badges to draw now, in `Activity` order."""
        return [
            Badge(f"{a.label} {self._details[a]}".strip(), a.color, self._blink_on)
            for a in Activity
            if a in self._details
        ]
