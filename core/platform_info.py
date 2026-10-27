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


def describe_platform() -> str:
    """Human-readable OS description (e.g. 'Linux-6.8.0-x86_64-with-glibc2.39'), for logs and bug reports."""
    return platform.platform()


@dataclass(frozen=True)
class PlatformProfile:
    """Everything that differs between the Windows build and the Linux
    (Debian-based) build lives in one of these."""

    platform: Platform
    default_backend: Optional[int]      # cv2.CAP_* constant preselected in the UI (None: first listed)
    default_stage_port: str


_PROFILES = {
    Platform.WINDOWS: PlatformProfile(
        platform=Platform.WINDOWS,
        default_backend=cv2.CAP_MSMF,
        default_stage_port="COM5",
    ),
    Platform.LINUX: PlatformProfile(
        platform=Platform.LINUX,
        default_backend=cv2.CAP_V4L2,
        default_stage_port="/dev/ttyACM0",
    ),
    Platform.MACOS: PlatformProfile(
        platform=Platform.MACOS,
        default_backend=cv2.CAP_AVFOUNDATION,
        default_stage_port="/dev/tty.usbmodem",
    ),
    Platform.UNKNOWN: PlatformProfile(
        platform=Platform.UNKNOWN,
        default_backend=None,
        default_stage_port="",
    ),
}


def current_profile() -> PlatformProfile:
    return _PROFILES[CURRENT_PLATFORM]
