"""
OFM Webcam Viewer — entry point.

Run from the repository root (the directory containing this file):
    python app.py
    python app.py --simulate
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

from ui.main_window import MainWindow


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="OFM Webcam Viewer")
    parser.add_argument(
        "--simulate", action="store_true",
        help="Run in simulation mode (mock stage controller)",
    )
    parser.add_argument(
        "--log-level", default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="Logging verbosity (default: INFO)",
    )
    return parser.parse_args(argv)


def main() -> None:
    args = parse_args(sys.argv[1:])
    logging.basicConfig(level=getattr(logging, args.log_level), format="%(levelname)s %(name)s: %(message)s")

    app = QApplication(sys.argv)
    window = MainWindow(simulation_mode=args.simulate)
    window.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
