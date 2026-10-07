"""
OFM Webcam Viewer — entry point.

Run from the repository root (the directory containing this file):
    python app.py                       # asks which mode to start in
    python app.py --mode camera-stage   # skip the dialog: camera + real stage
    python app.py --mode camera         # skip the dialog: camera only (no motors)
    python app.py --mode simulation     # skip the dialog: simulated stage
"""

from __future__ import annotations

import argparse
import logging
import sys

import cv2

# Quiet OpenCV's internal backend-probing log spam before any cv2.VideoCapture use.
try:
    cv2.utils.logging.setLogLevel(cv2.utils.logging.LOG_LEVEL_ERROR)
except Exception:
    pass

from PyQt5.QtWidgets import QApplication

from core.app_mode import AppMode
from ui.main_window import MainWindow
from ui.startup import resolve_session


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="OFM Webcam Viewer")
    parser.add_argument(
        "--mode", choices=[m.value for m in AppMode],
        help="Skip the startup dialog and launch directly in this mode",
    )
    parser.add_argument(
        "--simulate", action="store_true",
        help="Deprecated alias for --mode simulation",
    )
    parser.add_argument(
        "--stage-port", default=None, metavar="PORT",
        help="Serial port of the stage board (e.g. COM5, /dev/ttyACM0). "
             "Default: the platform default, then an automatic scan.",
    )
    parser.add_argument(
        "--log-level", default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="Logging verbosity (default: INFO)",
    )
    args = parser.parse_args(argv)
    if args.simulate and args.mode not in (None, AppMode.SIMULATION.value):
        parser.error("--simulate conflicts with --mode " + args.mode)
    return args


def main() -> None:
    args = parse_args(sys.argv[1:])
    logging.basicConfig(level=getattr(logging, args.log_level), format="%(levelname)s %(name)s: %(message)s")

    requested = AppMode(args.mode) if args.mode else (AppMode.SIMULATION if args.simulate else None)

    app = QApplication(sys.argv)
    session = resolve_session(requested, args.stage_port)
    if session is None:
        sys.exit(0)  # user closed the dialog or chose Quit

    window = MainWindow(session.mode, session.stage)
    window.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
