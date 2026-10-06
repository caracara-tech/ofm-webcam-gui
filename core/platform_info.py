"""
Single source of truth for "what platform are we running on".

Nothing else in the codebase should call `platform.system()` directly —
import `CURRENT_PLATFORM` / `PlatformProfile` from here instead. This keeps
platform-specific decisions (default ports, default camera backend, which
optional features are available) in one auditable place, which matters once
we're shipping separate Windows and Linux executables built from the same
source.
"""

from __future__ import annotations

import platform
from dataclasses import dataclass
from enum import Enum
from typing import Optional

import cv2


class Platform(str, Enum):
    WINDOWS = "windows"
    LINUX = "linux"
    MACOS = "macos"
    UNKNOWN = "unknown"


def detect_platform() -> Platform:
    system = platform.system()
    if system == "Windows":
        return Platform.WINDOWS
    if system == "Linux":
        return Platform.LINUX
    if system == "Darwin":
        return Platform.MACOS
    return Platform.UNKNOWN


CURRENT_PLATFORM: Platform = detect_platform()


@dataclass(frozen=True)
class PlatformProfile:
    """Everything that differs between the Windows build and the Linux
    (Debian-based) build lives in one of these."""

    platform: Platform
    default_backend_index: int          # index into core.config.BACKENDS
    default_stage_port: str
    default_arduino_port: str
    supports_camera_name_detection: bool  # pygrabber (Windows only)
    preferred_cv2_backend: Optional[int]  # used for the "Auto" fallback probe order


_PROFILES = {
    Platform.WINDOWS: PlatformProfile(
        platform=Platform.WINDOWS,
        default_backend_index=1,  # Media Foundation
        default_stage_port="COM5",
        default_arduino_port="COM12",
        supports_camera_name_detection=True,
        preferred_cv2_backend=cv2.CAP_MSMF,
    ),
    Platform.LINUX: PlatformProfile(
        platform=Platform.LINUX,
        default_backend_index=3,  # V4L2
        default_stage_port="/dev/ttyACM0",
        default_arduino_port="/dev/ttyACM0",
        supports_camera_name_detection=False,
        preferred_cv2_backend=cv2.CAP_V4L2,
    ),
    Platform.MACOS: PlatformProfile(
        platform=Platform.MACOS,
        default_backend_index=0,  # Auto
        default_stage_port="/dev/tty.usbmodem",
        default_arduino_port="/dev/tty.usbmodem",
        supports_camera_name_detection=False,
        preferred_cv2_backend=None,
    ),
    Platform.UNKNOWN: PlatformProfile(
        platform=Platform.UNKNOWN,
        default_backend_index=0,
        default_stage_port="",
        default_arduino_port="",
        supports_camera_name_detection=False,
        preferred_cv2_backend=None,
    ),
}


def current_profile() -> PlatformProfile:
    return _PROFILES[CURRENT_PLATFORM]
