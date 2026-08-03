"""
Static application configuration.

Nothing in this module has side effects on import (no cv2 backend probing,
no filesystem writes) so it's safe to import from anywhere, including tests.
"""

from __future__ import annotations

import platform
from pathlib import Path

import cv2

from core.types import CameraBackend, Resolution

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

DEFAULT_STAGE_PORT_WINDOWS = "COM5"
DEFAULT_STAGE_PORT_LINUX = "/dev/ttyACM0"
DEFAULT_ARDUINO_PORT_WINDOWS = "COM12"

SIMULATION_SPEED_MULTIPLIER = 10.0
SANGABOARD_MAX_STEPS_PER_SEC = 1000


def default_backend_index() -> int:
    system = platform.system()
    if system == "Windows":
        return 1  # Media Foundation
    if system == "Linux":
        return 3  # V4L2
    return 0  # Auto (macOS / unknown)


def default_stage_port() -> str:
    return DEFAULT_STAGE_PORT_WINDOWS if platform.system() == "Windows" else DEFAULT_STAGE_PORT_LINUX
