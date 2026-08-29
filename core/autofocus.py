"""
Pure, testable pieces of the Z-sweep autofocus routine.

The actual sweep needs a camera and a stage, so it has to be orchestrated by
something stateful (see `ui/threads/autofocus_thread.py`). Everything in
*this* module is deterministic and hardware-free: the focus metric and the
sequence of step offsets to visit. Keeping them here means they can be unit
tested without a camera, a stage, or Qt.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List

import cv2
import numpy as np


@dataclass(frozen=True)
class AutoFocusSettings:
    """User/UI-tunable parameters for one autofocus sweep."""

    range_steps: int = 15        # motor steps to search on either side of the start position
    step_size: int = 1           # motor steps per increment while sweeping
    delay_per_step_s: float = 0.01
    settle_s: float = 0.15       # pause after each move for a fresh frame to arrive


def focus_score(frame: np.ndarray) -> float:
    """Sharpness metric for one frame: variance of the Laplacian.

    Higher = sharper/more in-focus. This is a standard, cheap autofocus
    metric - blurry images have smoothly varying intensity (low second
    derivative), sharp images have strong edges (high second derivative).
    """
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY) if frame.ndim == 3 else frame
    return float(cv2.Laplacian(gray, cv2.CV_64F).var())


def sweep_offsets(range_steps: int) -> List[int]:
    """The sequence of Z offsets (in motor-step units, relative to the
    starting position) that a sweep should visit, in visiting order."""
    if range_steps <= 0:
        return [0]
    return list(range(-range_steps, range_steps + 1))


def best_offset(offsets: List[int], scores: List[float]) -> int:
    """Pick the offset with the highest focus score."""
    if len(offsets) != len(scores) or not offsets:
        raise ValueError("offsets and scores must be the same non-empty length")
    best_index = max(range(len(scores)), key=lambda i: scores[i])
    return offsets[best_index]
