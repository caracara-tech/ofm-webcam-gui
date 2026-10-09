"""Small desktop-integration helpers (things that need the operating system)."""

from __future__ import annotations

import logging
import sys
from pathlib import Path

from PyQt5.QtCore import QProcess, QProcessEnvironment, QUrl
from PyQt5.QtGui import QDesktopServices

logger = logging.getLogger(__name__)


def open_in_file_manager(folder: Path) -> bool:
    """Show `folder` in the system file manager (created first if missing).

    Returns False if nothing could be launched.
    """
    try:
        folder.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        logger.warning("Cannot create %s: %s", folder, exc)
        return False

    if sys.platform.startswith("linux") and getattr(sys, "frozen", False):
        return _open_with_xdg_open(folder)
    return QDesktopServices.openUrl(QUrl.fromLocalFile(str(folder)))


def _open_with_xdg_open(folder: Path) -> bool:
    """Linux executable built with PyInstaller: launch `xdg-open` with the
    library path the user's session had.

    PyInstaller points LD_LIBRARY_PATH at its own bundled libraries (and saves
    the original in LD_LIBRARY_PATH_ORIG). A file manager started with the
    modified value can crash on the wrong libraries, so restore the original.
    """
    env = QProcessEnvironment.systemEnvironment()
    original = env.value("LD_LIBRARY_PATH_ORIG")
    if original:
        env.insert("LD_LIBRARY_PATH", original)
    else:
        env.remove("LD_LIBRARY_PATH")
    process = QProcess()
    process.setProcessEnvironment(env)
    process.setProgram("xdg-open")
    process.setArguments([str(folder)])
    started, _pid = process.startDetached()
    return bool(started)
