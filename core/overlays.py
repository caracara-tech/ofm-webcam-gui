"""
Drawing helpers for the camera preview: an evenly-spaced alignment grid and
a scale bar. Each function takes a frame and returns a frame with no
hidden state and no Qt/hardware dependency - the same pure-input/
pure-output style as core/autofocus.py, so the geometry can be unit tested
without a running GUI.

Scale bar units: by default the scale bar reads in **pixels** (e.g.
"100 px") - this is fully automatic and needs no calibration, since it's
computed straight from the frame's own pixel dimensions. A **physical**
scale bar in real-world units (e.g. "50 um") additionally requires an
external reference measurement - there is no way to derive real-world
size from pixel counts alone, that's a property of optics, not something
software can compute around. If the caller has a calibrated `um_per_pixel`
value (see core/scale_calibration.py), pass it to get physical units;
otherwise `draw_scale_bar` falls back to the automatic pixel-count bar.

Note: labels are written in plain ASCII ("um", not the "u03bc"/mu-micro
symbol) - OpenCV's built-in Hershey fonts don't reliably render non-ASCII
glyphs, so a literal micro sign can come out as a missing/garbled
character depending on platform.
"""

from __future__ import annotations

from enum import Enum
from typing import List, Optional

import cv2
import numpy as np



class ScaleBarColor(str, Enum):
    """The colours the user can pick for the scale bar."""

    WHITE = "white"
    BLACK = "black"

    @property
    def bgr(self) -> tuple[int, int, int]:
        """The colour as an OpenCV (blue, green, red) tuple."""
        return (255, 255, 255) if self is ScaleBarColor.WHITE else (0, 0, 0)


GRID_COLOR = (0, 200, 0)
SCALE_BAR_COLOR = ScaleBarColor.WHITE.bgr  # default
_NICE_MULTIPLIERS = (1.0, 2.0, 5.0)


def grid_line_positions(size_px: int, spacing_px: int) -> List[int]:
    """1-D evenly spaced line positions covering (0, size_px), `spacing_px`
    apart. Pure geometry - no drawing - so it's trivial to unit test."""
    if spacing_px <= 0 or size_px <= 0:
        return []
    return list(range(spacing_px, size_px, spacing_px))


def draw_grid(frame: np.ndarray, spacing_px: int, color=GRID_COLOR, thickness: int = 1) -> np.ndarray:
    """Draw an evenly-spaced alignment grid over `frame` in place, and
    return it (for convenient chaining). Caller should pass a frame it's
    OK to mutate - e.g. a `.copy()` if the original must stay untouched."""
    h, w = frame.shape[:2]
    for x in grid_line_positions(w, spacing_px):
        cv2.line(frame, (x, 0), (x, h), color, thickness, cv2.LINE_AA)
    for y in grid_line_positions(h, spacing_px):
        cv2.line(frame, (0, y), (w, y), color, thickness, cv2.LINE_AA)
    return frame


def _nice_round_number(value: float) -> float:
    """Round `value` to the nearest 1/2/5 x a power of ten - e.g. 43.7 ->
    50, 0.031 -> 0.03. Shared by both the pixel and physical scale-bar
    length pickers so a bar always reads as a clean, easy number."""
    if value <= 0:
        return 0.0
    exponent = int(np.floor(np.log10(value)))
    best_value, best_diff = None, None
    for e in (exponent - 1, exponent, exponent + 1):
        for m in _NICE_MULTIPLIERS:
            candidate = m * (10.0 ** e)
            diff = abs(candidate - value)
            if best_diff is None or diff < best_diff:
                best_diff, best_value = diff, candidate
    return float(best_value)


def nice_scale_bar_length_px(frame_width_px: int, target_fraction: float = 0.2) -> int:
    """Pick a "nice" round pixel length (1/2/5 x a power of ten) close to
    `target_fraction` of the frame width, for the fully-automatic,
    zero-calibration pixel-count scale bar."""
    if frame_width_px <= 0:
        return 0
    return max(1, int(round(_nice_round_number(target_fraction * frame_width_px))))


def nice_scale_bar_length_um(um_per_pixel: float, frame_width_px: int, target_fraction: float = 0.2) -> float:
    """Pick a "nice" round physical length (1/2/5 x a power of ten) whose
    on-screen width is close to `target_fraction` of the frame width - the
    standard approach scientific imaging software uses so a scale bar reads
    "50 um" rather than an oddly-precise "43.7 um"."""
    if um_per_pixel <= 0 or frame_width_px <= 0:
        return 0.0
    return _nice_round_number(target_fraction * frame_width_px * um_per_pixel)


def draw_scale_bar(
    frame: np.ndarray,
    um_per_pixel: Optional[float] = None,
    *,
    color=SCALE_BAR_COLOR,
    margin_px: int = 20,
    thickness: int = 3,
) -> np.ndarray:
    """Draw a scale bar with a text label in the bottom-right corner of
    `frame`, in place, and return it.

    If `um_per_pixel` is a positive calibrated value, the bar reads in
    physical units (e.g. "50 um"). Otherwise (`None`, the automatic
    default) it reads in pixels (e.g. "100 px") - computed purely from the
    frame's own dimensions, no calibration required.
    """
    h, w = frame.shape[:2]

    if um_per_pixel is not None and um_per_pixel > 0:
        length_um = nice_scale_bar_length_um(um_per_pixel, w)
        if length_um <= 0:
            return frame
        length_px = max(1, int(round(length_um / um_per_pixel)))
        label = f"{length_um:g} um" if length_um >= 1 else f"{length_um * 1000:g} nm"
    else:
        length_px = nice_scale_bar_length_px(w)
        if length_px <= 0:
            return frame
        label = f"{length_px} px"

    x2 = w - margin_px
    x1 = max(0, x2 - length_px)
    y = h - margin_px

    cv2.line(frame, (x1, y), (x2, y), color, thickness, cv2.LINE_AA)
    cv2.line(frame, (x1, y - 6), (x1, y + 6), color, thickness, cv2.LINE_AA)  # end ticks
    cv2.line(frame, (x2, y - 6), (x2, y + 6), color, thickness, cv2.LINE_AA)

    text_size, _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.6, 2)
    text_x = x1 + max(0, (length_px - text_size[0]) // 2)
    text_y = y - 12
    cv2.putText(frame, label, (text_x, text_y), cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2, cv2.LINE_AA)
    return frame
