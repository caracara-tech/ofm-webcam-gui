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
    """User/UI-tunable parameters for a coarse-to-fine autofocus sweep.

    Range/step are specified in *physical* units (micrometres) rather than
    raw motor steps, because a fixed step count means wildly different
    physical distances on different stages/calibrations (e.g. Sangaboard's
    12.2 nm/step vs Arduino's 305.5 nm/step). Physical units are converted
    to steps per-stage via `AxisCalibration` right before a sweep runs -
    see `plan_autofocus_sweep` below.

    The search runs in two stages:

    1. Coarse: a wide, coarsely-sampled sweep to find the general region
       the true focus lies in. If the winner sits at the edge of the
       window (the true peak is probably further out), the window
       expands by `coarse_growth` and sweeps again from the new center -
       up to `max_coarse_passes` times. This finds a focus that's *far*
       away in only a couple of passes, instead of creeping toward it
       `range_um` at a time.
    2. Fine: once the coarse stage lands on an interior peak (not at an
       edge), one final narrow, finely-sampled sweep refines that to
       sub-coarse-step precision.
    """

    coarse_range_um: float = 30.0   # +/- distance for the initial coarse sweep
    coarse_step_um: float = 1.5     # distance per increment during the coarse sweep
    coarse_growth: float = 2.0      # multiply coarse_range_um by this each time it hits the edge
    max_coarse_passes: int = 5      # cap on coarse expansion passes
    fine_range_um: float = 3.0      # +/- distance for the final fine sweep
    fine_step_um: float = 0.25      # distance per increment during the fine sweep
    delay_per_step_s: float = 0.01
    settle_s: float = 0.15          # max wait after each move for a fresh frame to arrive
    roi_fraction: float = 0.5       # score a centered crop of this fraction of width/height


@dataclass(frozen=True)
class AutoFocusPlan:
    """Motor-step version of one sweep window, resolved for one stage's
    calibration. This is what `AutoFocusThread` actually sweeps over."""

    range_steps: int
    step_size: int


def plan_autofocus_sweep(range_um: float, step_um: float, nm_per_step: float) -> AutoFocusPlan:
    """Convert a physical-unit sweep window (+/- range_um, in step_um hops)
    into motor steps for a stage with the given Z calibration (nm/step).

    `range_steps` is a *position count* on either side of the start (how
    many sample points the sweep visits) - NOT a raw motor-step distance.
    Each of those positions is `step_size` raw motor steps apart, and
    `step_size` is what's derived from physical units via the calibration.
    So: step_size = step_um converted to steps; range_steps = how many of
    those step_um-sized hops fit in range_um.
    """
    if nm_per_step <= 0:
        raise ValueError("nm_per_step must be positive")
    if step_um <= 0:
        raise ValueError("step_um must be positive")
    step_size = max(1, int(round(step_um * 1000.0 / nm_per_step)))
    range_steps = max(1, int(round(range_um / step_um)))
    return AutoFocusPlan(range_steps=range_steps, step_size=step_size)


def crop_center(frame: np.ndarray, fraction: float) -> np.ndarray:
    """Return a centered crop covering `fraction` of the frame's width and
    height (e.g. 0.5 -> the middle 50% by width and 50% by height)."""
    if not 0 < fraction <= 1.0:
        raise ValueError("fraction must be in (0, 1]")
    if fraction >= 1.0:
        return frame
    h, w = frame.shape[:2]
    crop_h, crop_w = max(1, int(h * fraction)), max(1, int(w * fraction))
    y0 = (h - crop_h) // 2
    x0 = (w - crop_w) // 2
    return frame[y0 : y0 + crop_h, x0 : x0 + crop_w]


def focus_score(frame: np.ndarray, roi_fraction: float = 1.0) -> float:
    """Sharpness metric for one frame: variance of the Laplacian.

    Higher = sharper/more in-focus. This is a standard, cheap autofocus
    metric - blurry images have smoothly varying intensity (low second
    derivative), sharp images have strong edges (high second derivative).

    Scoring is done on a centered crop (`roi_fraction` of width/height,
    default full frame) rather than the whole frame. Background clutter,
    lens vignetting, and anything outside the actual sample don't get
    sharper or blurrier as the sample comes into focus - they just add
    noise to the metric and blunt the peak the sweep is trying to find.
    Restricting scoring to the region that actually contains the subject
    makes the peak sharper and easier to locate in fewer passes.
    """
    cropped = crop_center(frame, roi_fraction) if roi_fraction < 1.0 else frame
    gray = cv2.cvtColor(cropped, cv2.COLOR_BGR2GRAY) if cropped.ndim == 3 else cropped
    return float(cv2.Laplacian(gray, cv2.CV_64F).var())


def sweep_offsets(range_steps: int) -> List[int]:
    """The sequence of Z offsets (in motor-step units, relative to the
    starting position) that a sweep should visit, in visiting order."""
    if range_steps <= 0:
        return [0]
    return list(range(-range_steps, range_steps + 1))


def best_offset(offsets: List[int], scores: List[float]) -> int:
    """Pick the offset with the highest focus score.

    Ties are broken toward the offset closest to the center (zero), not
    toward whichever tied offset happens to appear first in the list. The
    naive `max(..., key=...)` tie-break always keeps the *first* match,
    which for `sweep_offsets` is always the most-negative offset - so on a
    perfectly flat/tied score curve (no detectable focus signal at all,
    e.g. everything in the window is uniformly out of focus) it would
    always "win" toward the negative end. Combined with edge-triggered
    window expansion, that silently commits to a direction with no actual
    evidence behind it and can walk the stage further from focus, not
    closer. Preferring the smallest-|offset| tie keeps a no-information
    sweep from claiming a direction it doesn't actually have.
    """
    if len(offsets) != len(scores) or not offsets:
        raise ValueError("offsets and scores must be the same non-empty length")
    max_score = max(scores)
    tied = [offsets[i] for i, sc in enumerate(scores) if sc == max_score]
    return min(tied, key=abs)


def has_weak_signal(scores: List[float], min_relative_spread: float = 0.05) -> bool:
    """True if a sweep's scores barely vary across the whole window - i.e.
    the window doesn't actually contain the in-focus transition at all
    (still uniformly, deeply out of focus everywhere it looked). In that
    case whichever offset "won" isn't meaningful evidence of a direction;
    the search should keep expanding rather than trust it."""
    if not scores:
        return True
    lo, hi = min(scores), max(scores)
    if hi <= 0:
        return True
    return (hi - lo) / hi < min_relative_spread


def is_at_search_boundary(chosen: int, range_steps: int) -> bool:
    """True if the winning offset sits at either edge of the swept range.

    A hill-climb over a *fixed, finite* window can only ever report the
    best point *it looked at*. If that point is the very edge of the
    window, the true peak may well lie further out in that direction -
    the sweep hasn't actually bracketed a maximum, it's been clipped by
    its own search range. Autofocus should notice this and re-center on
    the new position for another pass, rather than reporting "done" and
    leaving the caller to notice and click again.
    """
    return abs(chosen) >= range_steps
