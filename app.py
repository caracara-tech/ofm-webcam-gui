"""
OFM Webcam Viewer — entry point.

Run from the repository root (the directory containing this file):
    python app.py                       # asks which mode to start in
    python app.py --mode automated      # skip the dialog: camera + real stage
    python app.py --mode manual         # skip the dialog: camera only (no motors)
    python app.py --mode simulation     # simulated stage (command line only)
    python app.py --lang es_419         # interface language for this run
    python app.py --save-log            # also write the session log to a file
    python app.py --help                # what this software can do
"""

from __future__ import annotations

import argparse
import logging
import os
import sys
from pathlib import Path
from typing import Optional

from core.app_mode import AppMode
from core.config import DEFAULT_LOG_DIR, DEFAULT_OUTPUT_DIR
from core.i18n import available_languages, match_language, resolve_language
from core.logging_setup import LogSession, configure_logging, describe_environment, install_excepthook
from core.platform_info import describe_platform
from core.version import __version__

logger = logging.getLogger("app")

# How the user started us: "python app.py" from a source checkout, otherwise the
# command's own name (a PyInstaller executable, or the pip-installed `ofm-webcam-gui`).
RUN_CMD = "python app.py" if Path(sys.argv[0]).name == "app.py" else Path(sys.argv[0]).name

DESCRIPTION = """\
OFM Webcam Viewer: a desktop GUI for OpenFlexure-style microscopes.

Live camera preview with snapshots and video recording, plus optional
motorized stage control (XY jog, Z focus, autofocus) through a Sangaboard.
Runs the same way on Windows, Linux and macOS."""


def _languages() -> str:
    return ", ".join(f"{lang.code} ({lang.name})" for lang in available_languages())


def _epilog() -> str:
    return f"""\
MODES  (pick one in the startup dialog, or skip it with --mode)
  automated     The full microscope: live camera and real stage control.
                Needs the stage board connected; if it cannot be reached you
                are asked to retry, choose another mode, or quit. If it
                stops responding while running, an error is shown and the
                stage controls are disabled.
  manual        For devices without motors: camera preview, snapshots and
                recording. Stage controls are not shown.
  simulation    Command line only (not listed in the startup dialog). No
                hardware needed: the full interface with a simulated stage;
                nothing physical moves. Handy for trying the software.
  The "Change mode / language..." button in the window returns to the
  startup dialog without closing the program.

FEATURES
  Camera        Choose the camera by name, the backend (Windows: Media
                Foundation or DirectShow) and the resolution (up to
                1280 x 720), then Start Stream. The refresh button rereads
                the camera list. If the camera cannot be opened the image
                box says "Camera not detected": pick another device or
                backend and press Start Stream again.
  Capture       PNG snapshots and MP4 recording (blinking REC marker in the
                preview only), optional burned-in timestamp.
                Output folder: {DEFAULT_OUTPUT_DIR}  (change with Browse,
                show its files with Open folder).
  Display       Alignment grid (preview only, never saved) and scale bar
                (saved into snapshots/recordings), in white or black. The
                scale bar reads in pixels by default, or in um with a
                physical calibration.
  Language      The interface language is chosen in the startup dialog and
                remembered for next time, or forced for one run with --lang.
                Installed: {_languages()}. Only the interface is translated;
                this help text and the framing of the log lines stay in
                English (a message that is also shown in the window is
                logged as shown).
  Log           Everything the program logs is kept for the session and can
                be read in the window ("View log..." in the status bar). Save
                it with --save-log or the "Save log to file" box: the file
                is created with the whole session so far, and unticking the
                box deletes it again (recording continues). Default folder:
                {DEFAULT_LOG_DIR}
  License       GNU General Public License v3; "About / License" at the
                bottom right of the window shows the full text.
  Stage         (automated and simulation modes) U/D/L/R for XY and
                W/S for Z focus, with step size (um), speed (um/s) and a
                live position readout. Autofocus runs a coarse-to-fine Z
                sweep and can optionally re-run after every XY move; it
                needs the camera stream running.

EXAMPLES
  {RUN_CMD}
      choose the mode in a dialog
  {RUN_CMD} --mode manual
      device without motors, no dialog
  {RUN_CMD} --mode automated --stage-port COM5
  {RUN_CMD} --mode simulation --log-level DEBUG
  {RUN_CMD} --save-log
      write the session log to {DEFAULT_LOG_DIR}
  {RUN_CMD} --save-log ~/lab/run1.log --log-level DEBUG
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
        help="Skip the startup dialog and launch directly in this mode "
             "(simulation is only available this way)",
    )
    parser.add_argument(
        "--simulate", action="store_true",
        help="Shorthand for --mode simulation",
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
        help="Logging verbosity, for the console, the in-window log and the log file (default: INFO)",
    )
    parser.add_argument(
        "--save-log", nargs="?", const="", default=None, metavar="PATH",
        help="Also write the session log to a file. PATH is a file, or a folder to put a "
             "timestamped file in; without PATH the default log folder is used. "
             "Can also be switched on later with the \"Save log to file\" box in the window.",
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

    # Logging next, so anything that goes wrong while importing or starting up
    # is already recorded (and can be saved with --save-log).
    save_path = os.path.expanduser(args.save_log) if args.save_log else None  # raw text: keeps a trailing "/"
    log_session = configure_logging(
        args.log_level, DEFAULT_LOG_DIR, save=args.save_log is not None, path=save_path,
    )
    install_excepthook()
    logger.info("OFM Webcam Viewer v%s | %s | %s", __version__, describe_platform(), describe_environment())
    logger.info("Arguments: %s", " ".join(sys.argv[1:]) or "(none)")

    try:
        exit_code = _run(args, log_session)
    finally:
        log_session.close()
    sys.exit(exit_code)


def _run(args: argparse.Namespace, log_session: LogSession) -> int:
    import cv2

    # Quiet OpenCV's internal backend-probing log spam before any cv2.VideoCapture use.
    try:
        cv2.utils.logging.setLogLevel(cv2.utils.logging.LOG_LEVEL_ERROR)
    except Exception:
        pass

    from PyQt5.QtCore import PYQT_VERSION_STR, QT_VERSION_STR
    from PyQt5.QtWidgets import QApplication

    from ui.language import apply_language, saved_language, system_locale

    logger.info("OpenCV %s | Qt %s | PyQt %s", cv2.__version__, QT_VERSION_STR, PYQT_VERSION_STR)

    requested = AppMode(args.mode) if args.mode else (AppMode.SIMULATION if args.simulate else None)

    app = QApplication(sys.argv)
    # Priority: --lang, then the remembered choice, then the OS language, then English.
    language = apply_language(resolve_language(args.lang, saved_language(), system_locale()))
    logger.info("Interface language: %s", language)
    return run_sessions(app, requested, args.stage_port, log_session)


def run_sessions(app, requested: Optional[AppMode], stage_port: Optional[str], log_session: LogSession) -> int:
    """Run one window per session until the user quits; returns the exit code.

    `requested` (the command-line mode, if any) only applies to the first
    session. After "Change mode / language..." the window reports the mode
    picked on the start screen (`next_mode`) and we start it, without the
    program ever closing. The log session outlives the windows, so the log
    (and the log file, if on) covers every session of the run.
    """
    from ui.main_window import MainWindow
    from ui.startup import choose_mode

    exit_code = 0
    while True:
        mode = choose_mode(requested)
        if mode is None:
            logger.info("No mode chosen; exiting")
            return exit_code  # the user closed the dialog
        window = MainWindow(mode, log_session, stage_port=stage_port)
        window.show()
        exit_code = app.exec_()
        requested = window.next_mode
        if requested is None:
            logger.info("Window closed; exiting with code %s", exit_code)
            return exit_code


if __name__ == "__main__":
    main()
