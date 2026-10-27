"""Facts about the application itself: its name and its license.

No Qt in here. The About dialog shows them.
"""

from __future__ import annotations

import logging
from importlib import metadata
from pathlib import Path
from typing import Optional

from core.i18n import N_

APP_NAME = "OFM Webcam Viewer"
DISTRIBUTION_NAME = "ofm-webcam-gui"  # the pip package name (see pyproject.toml)
LICENSE_NAME = "GNU General Public License, version 3"
LICENSE_SPDX = "GPL-3.0"
LICENSE_URL = "https://www.gnu.org/licenses/gpl-3.0.html"

# Marked for translation here, translated where it is shown (see core/i18n.py).
LICENSE_NOTICE = N_(
    "This program is free software, released under the GNU General Public License, "
    "version 3. You may redistribute it and/or modify it under the terms of that "
    "license. It comes with ABSOLUTELY NO WARRANTY; see the license text below."
)

logger = logging.getLogger(__name__)

# LICENSE sits at the repository root. In a PyInstaller build the spec places
# it at the root of the bundle, which is exactly where `core/` resolves to.
_LICENSE_FILE = Path(__file__).resolve().parent.parent / "LICENSE"


def load_license_text() -> Optional[str]:
    """The full license text, or None if it cannot be found anywhere.

    Looked up in this order: the LICENSE file next to the code (source checkout
    and PyInstaller builds), then the installed package's metadata (pip installs).
    """
    try:
        return _LICENSE_FILE.read_text(encoding="utf-8")
    except OSError:
        pass
    try:
        distribution = metadata.distribution(DISTRIBUTION_NAME)
        for name in ("LICENSE", "licenses/LICENSE"):
            text = distribution.read_text(name)
            if text:
                return text
    except Exception as exc:  # not installed as a package, or unreadable metadata
        logger.debug("License text not available from package metadata: %s", exc)
    return None
