"""
OFM Webcam Viewer — entry point.

Run from the repository root (the directory containing this file):
    python app.py                       # asks which mode to start in
    python app.py --mode camera-stage   # skip the dialog: camera + real stage
    python app.py --mode camera         # skip the dialog: camera only (no motors)
    python app.py --mode simulation     # skip the dialog: simulated stage
    python app.py --lang es_419         # interface language for this run
    python app.py --help                # what this software can do
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

from core.app_mode import AppMode
from core.config import DEFAULT_OUTPUT_DIR
from core.i18n import available_languages, match_language, resolve_language

# "python app.py" from source, the executable's own name when frozen by PyInstaller.
RUN_CMD = Path(sys.executable).name if getattr(sys, "frozen", False) else "python app.py"

DESCRIPTION = """\
OFM Webcam Viewer: a desktop GUI for OpenFlexure-style microscopes.

Live camera preview with snapshots and video recording, plus optional
motorized stage control (XY jog, Z focus, autofocus) through a Sangaboard.
Runs the same way on Windows and Linux."""


def _languages() -> str:
    return ", ".join(f"{lang.code} ({lang.name})" for lang in available_languages())


def _epilog() -> str:
    return f"""\
MODES  (pick one in the startup dialog, or skip it with --mode)
  camera-stage  Camera + Stage. The full microscope: live camera and real
                stage control. Needs the stage board connected; if it
                cannot be reached you are asked to retry, choose another
                mode, or quit. If it stops responding while running, an
                error is shown and the stage controls are disabled.
  camera        Camera only, for devices without motors. Stage controls are
                not shown.
  simulation    No hardware needed. Full interface with a simulated stage;
                nothing physical moves. Handy for trying the software.

FEATURES
  Camera        Choose device index, backend (Windows: Media Foundation or
                DirectShow) and resolution (up to 1280 x 720), then Start
                Stream. Live FPS is shown in the status bar. If the camera
                cannot be opened the image box says "Camera not detected":
                try another device index and press Start Stream again.
  Capture       PNG snapshots and MP4 recording (blinking REC marker in the
                preview only), optional burned-in timestamp.
                Output folder: {DEFAULT_OUTPUT_DIR}  (change with Browse).
  Display       Alignment grid (preview only, never saved) and scale bar
                (saved into snapshots/recordings). The scale bar reads in
                pixels by default, or in um with a physical calibration.
  Language      The interface language is chosen in the startup dialog and
                remembered for next time, or forced for one run with --lang.
                Installed: {_languages()}. Only the interface is translated;
                this help text and the log output stay in English.
  Stage         (camera-stage and simulation modes) U/D/L/R for XY and
                W/S for Z focus, with step size (um), speed (um/s) and a
                live position readout. Autofocus runs a coarse-to-fine Z
                sweep and can optionally re-run after every XY move; it
                needs the camera stream running.

EXAMPLES
  {RUN_CMD}
      choose the mode in a dialog
  {RUN_CMD} --mode camera
      camera-only device, no dialog
  {RUN_CMD} --mode camera-stage --stage-port COM5
  {RUN_CMD} --mode simulation --log-level DEBUG
  {RUN_CMD} --lang es_419
"""


class _Parser(argparse.ArgumentParser):
    """Prints help/errors to the console, or in a dialog when there is no console.

    The Windows executable is built windowed (no terminal), where stdout and
    stderr do not exist and argparse's output would otherwise vanish.
    """

    def print_help(self, file=None) -> None:
        _show_text(self.format_help(), "OFM Webcam Viewer - help", error=False)

    def error(self, message: str) -> None:
        _show_text(f"{self.format_usage()}\nerror: {message}\n", "OFM Webcam Viewer - invalid arguments", error=True)
        sys.exit(2)


def _show_text(text: str, title: str, error: bool) -> None:
    stream = sys.stderr if error else sys.stdout
    if stream is not None:
        stream.write(text)
        return
    _show_text_dialog(text, title)


def _show_text_dialog(text: str, title: str) -> None:
    from PyQt5.QtGui import QFontDatabase
    from PyQt5.QtWidgets import QApplication, QDialog, QPlainTextEdit, QPushButton, QVBoxLayout

    app = QApplication.instance() or QApplication(sys.argv)
    dialog = QDialog()
    dialog.setWindowTitle(title)
    dialog.resize(760, 640)
    layout = QVBoxLayout(dialog)
    view = QPlainTextEdit(text)
    view.setReadOnly(True)
    view.setFont(QFontDatabase.systemFont(QFontDatabase.FixedFont))
    view.setLineWrapMode(QPlainTextEdit.NoWrap)
    layout.addWidget(view)
    close = QPushButton("Close")
    close.clicked.connect(dialog.accept)
    layout.addWidget(close)
    dialog.exec_()
    del app


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = _Parser(
        prog=RUN_CMD,
        description=DESCRIPTION,
        epilog=_epilog(),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
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
        "--lang", default=None, metavar="CODE",
        help="Interface language for this run (installed: "
             + ", ".join(lang.code for lang in available_languages())
             + "). Overrides the remembered choice without changing it.",
    )
    parser.add_argument(
        "--log-level", default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="Logging verbosity (default: INFO)",
    )
    args = parser.parse_args(argv)
    if args.lang and match_language(args.lang) is None:
        parser.error(
            f"unknown language {args.lang!r}; installed: "
            + ", ".join(lang.code for lang in available_languages())
        )
    if args.simulate and args.mode not in (None, AppMode.SIMULATION.value):
        parser.error("--simulate conflicts with --mode " + args.mode)
    return args


def main() -> None:
    # Parse first: --help and argument errors must work without opening a
    # window, a camera or even importing the GUI stack.
    args = parse_args(sys.argv[1:])

    import cv2

    # Quiet OpenCV's internal backend-probing log spam before any cv2.VideoCapture use.
    try:
        cv2.utils.logging.setLogLevel(cv2.utils.logging.LOG_LEVEL_ERROR)
    except Exception:
        pass

    from PyQt5.QtWidgets import QApplication

    from ui.language import apply_language, saved_language, system_locale
    from ui.main_window import MainWindow
    from ui.startup import resolve_session

    logging.basicConfig(level=getattr(logging, args.log_level), format="%(levelname)s %(name)s: %(message)s")

    requested = AppMode(args.mode) if args.mode else (AppMode.SIMULATION if args.simulate else None)

    app = QApplication(sys.argv)
    # Priority: --lang, then the remembered choice, then the OS language, then English.
    apply_language(resolve_language(args.lang, saved_language(), system_locale()))
    session = resolve_session(requested, args.stage_port)
    if session is None:
        sys.exit(0)  # user closed the dialog or chose Quit

    window = MainWindow(session.mode, session.stage)
    window.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
