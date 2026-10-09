"""Which cameras are connected, and what are they called.

Gives the camera dropdown readable names instead of bare numbers.

  - Windows: names come from DirectShow through the optional `pygrabber`
    package (listed in requirements/windows.txt). Their order is the device
    index OpenCV uses.
  - Linux: names are read from /sys/class/video4linux (no extra package).
    A camera's index is the N of its /dev/videoN node.
  - Other platforms: no listing; the UI falls back to generic entries.

Isolating this here keeps the UI free of platform checks and keeps `pygrabber`
out of Linux builds entirely.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

from core.i18n import _
from core.platform_info import CURRENT_PLATFORM, Platform

logger = logging.getLogger(__name__)

SYSFS_VIDEO4LINUX = Path("/sys/class/video4linux")


@dataclass(frozen=True)
class CameraDevice:
    index: int  # the device index OpenCV's VideoCapture expects
    name: str


@dataclass(frozen=True)
class CameraListing:
    devices: List[CameraDevice]
    note: Optional[str] = None  # why the list may be missing or incomplete; shown as a tooltip


def list_cameras() -> CameraListing:
    """The cameras this computer reports, sorted by device index."""
    if CURRENT_PLATFORM == Platform.WINDOWS:
        return _list_windows()
    if CURRENT_PLATFORM == Platform.LINUX:
        return _list_linux()
    return CameraListing([])


def _list_windows() -> CameraListing:
    try:
        from pygrabber.dshow_graph import FilterGraph
    except ImportError:
        return CameraListing(
            [], _("Camera names need the optional 'pygrabber' package (pip install pygrabber).")
        )
    try:
        names = FilterGraph().get_input_devices()
    except Exception as exc:  # depends on the OS device state
        logger.warning("Listing cameras failed: %s", exc)
        return CameraListing([], str(exc))
    return CameraListing([CameraDevice(index, name) for index, name in enumerate(names)])


def _list_linux(sysfs: Path = SYSFS_VIDEO4LINUX) -> CameraListing:
    devices: List[CameraDevice] = []
    if not sysfs.is_dir():
        return CameraListing(devices)
    for node in sysfs.glob("video*"):
        number = node.name[len("video"):]
        if not number.isdigit():
            continue
        # One physical camera usually exposes several /dev/video nodes (video,
        # metadata, ...). Only the one with index 0 delivers pictures.
        try:
            if int((node / "index").read_text().strip()) != 0:
                continue
        except (OSError, ValueError):
            pass  # no index file: assume it is a normal capture node
        try:
            name = (node / "name").read_text().strip() or _("Camera {index}").format(index=number)
        except OSError:
            name = _("Camera {index}").format(index=number)
        devices.append(CameraDevice(int(number), name))
    return CameraListing(sorted(devices, key=lambda d: d.index))
