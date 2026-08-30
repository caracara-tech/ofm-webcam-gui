"""
Optional physical-scale (um-per-pixel) override for the camera preview's
scale bar.

By default, the scale bar (core/overlays.py::draw_scale_bar) reads in
pixels - fully automatic, computed straight from the frame's own
dimensions, no calibration needed. There's no way to derive real-world
physical size from pixel counts alone; that requires an external
reference measurement no software can substitute for. This module exists
for the person who *has* that reference (e.g. imaged a stage micrometer
once) and wants the scale bar to read in real units instead.

This setup's objective has no zoom, and Z only refocuses by moving the
sample - so if a physical calibration is supplied, it's a single fixed
constant, not a function of Z.
"""

from __future__ import annotations

MIN_UM_PER_PIXEL = 1e-6


def validate_um_per_pixel(value: float) -> float:
    """Validate a user-entered um/pixel override value, clamped to a
    positive minimum so a stray zero/negative can't silently produce a
    zero-length or negative-length scale bar."""
    if value <= 0:
        raise ValueError("um-per-pixel must be a positive number")
    return max(value, MIN_UM_PER_PIXEL)
