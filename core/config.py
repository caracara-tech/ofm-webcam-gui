"""
Static application configuration.

Nothing in this module has side effects on import (no cv2 backend probing,
no filesystem writes) so it's safe to import from anywhere, including tests.

Platform-specific defaults (ports, preferred backend) are NOT decided here —
they come from `core.platform_info.current_profile()`, which is the single
place that inspects the OS. This file just exposes the platform-independent
menus (all resolutions are offered on every OS; the profile only picks the
*default* camera backend).
"""

from __future__ import annotations

import sys
from pathlib import Path

import cv2

from .platform_info import CURRENT_PLATFORM, Platform, current_profile
from .types import CameraBackend, Resolution

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def _default_output_dir() -> Path:
    """Where snapshots/recordings go unless the user picks another folder.

    Running from a source checkout: <repo>/gallery (next to the code). Anywhere
    else (a PyInstaller executable, whose files live in a temp dir that is
    deleted on exit, or a pip-installed copy under site-packages, which is not
    meant to be written to): the user's Pictures folder.
    """
    from_source_checkout = not getattr(sys, "frozen", False) and (PROJECT_ROOT / "pyproject.toml").is_file()
    return PROJECT_ROOT / "gallery" if from_source_checkout else Path.home() / "Pictures" / "ofm-webcam-gui"


DEFAULT_OUTPUT_DIR = _default_output_dir()

RESOLUTIONS: list[Resolution] = [
    Resolution("1280 x 720", 1280, 720),
    Resolution("960 x 544", 960, 544),
    Resolution("800 x 600", 800, 600),
    Resolution("640 x 480", 640, 480),
    Resolution("320 x 240", 320, 240),
]

BACKENDS: list[CameraBackend] = [
    CameraBackend("Media Foundation - MSMF (Windows)", cv2.CAP_MSMF),
    CameraBackend("DirectShow - DSHOW (Windows, fallback)", cv2.CAP_DSHOW),
    CameraBackend("V4L2 (Linux)", cv2.CAP_V4L2),
    CameraBackend("AVFoundation (macOS)", cv2.CAP_AVFOUNDATION),
]

# Which backends make sense on each platform, so the combo box is free of
# options that can never work on the OS the app is running on. There is
# deliberately no "automatic" choice: the user picks the backend.
_BACKENDS_BY_PLATFORM = {
    Platform.WINDOWS: (cv2.CAP_MSMF, cv2.CAP_DSHOW),
    Platform.LINUX: (cv2.CAP_V4L2,),
    Platform.MACOS: (cv2.CAP_AVFOUNDATION,),
    Platform.UNKNOWN: tuple(b.cv2_flag for b in BACKENDS),
}

SIMULATION_SPEED_MULTIPLIER = 10.0
SANGABOARD_MAX_STEPS_PER_SEC = 1000


def platform_backends() -> list[CameraBackend]:
    """The backends relevant to the platform we're running on, in display order."""
    flags = _BACKENDS_BY_PLATFORM[CURRENT_PLATFORM]
    return [backend for backend in BACKENDS if backend.cv2_flag in flags]


def default_backend_position() -> int:
    """Index of the platform's default backend within platform_backends()."""
    default = current_profile().default_backend
    for position, backend in enumerate(platform_backends()):
        if backend.cv2_flag == default:
            return position
    return 0


def default_stage_port() -> str:
    return current_profile().default_stage_port


def default_arduino_port() -> str:
    return current_profile().default_arduino_port
