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

import sys
from pathlib import Path

import cv2

from .platform_info import CURRENT_PLATFORM, Platform, current_profile
from .types import CameraBackend, Resolution

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if getattr(sys, "frozen", False):
    # PyInstaller: __file__ lives in a temp dir that is deleted on exit (onefile),
    # and /usr/bin or Program Files is not writable -> save under the user's home.
    DEFAULT_OUTPUT_DIR = Path.home() / "Pictures" / "ofm-webcam-gui"
else:
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

# Which BACKENDS entries make sense on each platform. "Auto" (index 0) is
# always offered as a safe fallback. This keeps the combo box free of
# options that can never work on the OS the app is actually running on.
_BACKEND_INDICES_BY_PLATFORM = {
    Platform.WINDOWS: (0, 1, 2),  # Auto, MSMF, DSHOW
    Platform.LINUX: (0, 3),       # Auto, V4L2
    Platform.MACOS: (0,),         # Auto only - no dedicated backend wired up yet
    Platform.UNKNOWN: (0,),
}

SIMULATION_SPEED_MULTIPLIER = 10.0
SANGABOARD_MAX_STEPS_PER_SEC = 1000


def platform_backends() -> list[CameraBackend]:
    """The subset of BACKENDS relevant to the platform we're running on."""
    indices = _BACKEND_INDICES_BY_PLATFORM[CURRENT_PLATFORM]
    return [BACKENDS[i] for i in indices]


def default_backend_index() -> int:
    return current_profile().default_backend_index


def default_backend_position() -> int:
    """Index of the platform's default backend *within* platform_backends()
    (as opposed to default_backend_index(), which indexes the full BACKENDS
    list). Use this one when populating a combo box built from
    platform_backends()."""
    full_index = default_backend_index()
    for position, backend in enumerate(platform_backends()):
        if backend is BACKENDS[full_index]:
            return position
    return 0


def default_stage_port() -> str:
    return current_profile().default_stage_port


def default_arduino_port() -> str:
    return current_profile().default_arduino_port
