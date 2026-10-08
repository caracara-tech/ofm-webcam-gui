"""
Camera device name detection.

This capability only exists on Windows (via the optional `pygrabber`
package / DirectShow). Isolating it here means:
  - The UI layer doesn't need `if platform.system() == "Windows"` checks or
    a `try: import pygrabber` block of its own.
  - On Linux builds, `pygrabber` is simply never imported, so it doesn't
    need to be present at all (and isn't listed in the Linux requirements).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import List, Optional

from core.i18n import _
from core.platform_info import current_profile

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class CameraNameDetectionResult:
    supported: bool
    names: Optional[List[str]] = None
    error: Optional[str] = None


def is_supported() -> bool:
    return current_profile().supports_camera_name_detection


def detect_camera_names() -> CameraNameDetectionResult:
    """Attempt to list camera device names in index order.

    Returns `supported=False` (with no error) on platforms where this
    feature doesn't exist at all, so callers can distinguish "not available
    here" from "available but failed"."""
    if not is_supported():
        return CameraNameDetectionResult(supported=False)

    try:
        from pygrabber.dshow_graph import FilterGraph
    except ImportError:
        return CameraNameDetectionResult(
            supported=True,
            error=_("The optional 'pygrabber' package is not installed (pip install pygrabber)."),
        )

    try:
        names = FilterGraph().get_input_devices()
    except Exception as exc:  # pragma: no cover - depends on OS device state
        logger.warning("Camera name detection failed: %s", exc)
        return CameraNameDetectionResult(supported=True, error=str(exc))

    return CameraNameDetectionResult(supported=True, names=list(names))
