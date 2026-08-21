"""
Static application configuration.

Nothing in this module has side effects on import (no cv2 backend probing,
no filesystem writes) so it's safe to import from anywhere, including tests.

Platform-specific defaults (ports, preferred backend) are NOT decided here —
they come from `core.platform_info.current_profile()`, which is the single
place that inspects the OS. This file just exposes the platform-independent
menus (all resolutions/backends are offered on every OS; the profile only
picks a *default* index).
"""

from __future__ import annotations

from pathlib import Path

import cv2

from .platform_info import current_profile
from .types import CameraBackend, Resolution

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "gallery"

RESOLUTIONS: list[Resolution] = [
    Resolution("1280 x 720", 1280, 720),
    Resolution("960 x 544", 960, 544),
    Resolution("800 x 600", 800, 600),
    Resolution("640 x 480", 640, 480),
    Resolution("320 x 240", 320, 240),
]

BACKENDS: list[CameraBackend] = [
    CameraBackend("Auto", None),
    CameraBackend("Media Foundation - MSMF (Windows, recommended)", cv2.CAP_MSMF),
    CameraBackend("DirectShow - DSHOW (Windows, fallback)", cv2.CAP_DSHOW),
    CameraBackend("V4L2 (Linux)", cv2.CAP_V4L2),
]

SIMULATION_SPEED_MULTIPLIER = 10.0
SANGABOARD_MAX_STEPS_PER_SEC = 1000


def default_backend_index() -> int:
    return current_profile().default_backend_index


def default_stage_port() -> str:
    return current_profile().default_stage_port


def default_arduino_port() -> str:
    return current_profile().default_arduino_port
