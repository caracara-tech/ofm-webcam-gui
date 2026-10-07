"""Launch-time flow: pick an operating mode and, for Camera + Stage, connect the stage.

Runs before MainWindow exists, so a stage that cannot be reached is
reported explicitly (retry / pick another mode / quit) instead of the app
quietly opening in a different mode.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QApplication, QDialog, QLabel, QMessageBox, QPushButton, QVBoxLayout

from core.app_mode import AppMode
from hardware.abstract import StageController
from hardware.errors import StageCommunicationError
from hardware.stage import connect_real_stage, create_mock_stage


@dataclass
class Session:
    mode: AppMode
    stage: Optional[StageController]  # None only in camera-only mode


class ModeDialog(QDialog):
    """Three big buttons, one per AppMode. Closing the window cancels."""

    def __init__(self, default: AppMode = AppMode.CAMERA_STAGE) -> None:
        super().__init__()
        self.setWindowTitle("OFM Webcam Viewer \u2014 select mode")
        self.setMinimumWidth(460)
        self.selected: Optional[AppMode] = None

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("<b>How is this device set up?</b>"))

        self.buttons: dict[AppMode, QPushButton] = {}
        for mode in (AppMode.CAMERA_STAGE, AppMode.CAMERA_ONLY, AppMode.SIMULATION):
            btn = QPushButton(f"{mode.label}\n{mode.description}")
            btn.setStyleSheet("text-align: left; padding: 10px;")
            btn.clicked.connect(lambda _checked=False, m=mode: self._choose(m))
            if mode is default:
                btn.setDefault(True)
            layout.addWidget(btn)
            self.buttons[mode] = btn

    def _choose(self, mode: AppMode) -> None:
        self.selected = mode
        self.accept()

    @classmethod
    def ask(cls) -> Optional[AppMode]:
        dialog = cls()
        dialog.exec_()
        return dialog.selected


def _ask_after_stage_failure(message: str) -> str:
    """Returns 'retry', 'change' or 'quit'."""
    box = QMessageBox(QMessageBox.Critical, "Stage not available", message)
    box.setInformativeText("Camera + Stage mode needs the stage board. What would you like to do?")
    retry = box.addButton("Retry", QMessageBox.AcceptRole)
    change = box.addButton("Choose another mode", QMessageBox.ActionRole)
    quit_btn = box.addButton("Quit", QMessageBox.RejectRole)
    box.setDefaultButton(retry)
    box.exec_()
    clicked = box.clickedButton()
    if clicked is retry:
        return "retry"
    if clicked is change:
        return "change"
    return "quit" if clicked is quit_btn else "quit"


def resolve_session(requested: Optional[AppMode], stage_port: Optional[str] = None) -> Optional[Session]:
    """Pick the mode (dialog unless `requested` is given) and build the stage for it.

    Returns None if the user cancelled or quit. Needs a QApplication.
    """
    mode = requested
    while True:
        if mode is None:
            mode = ModeDialog.ask()
            if mode is None:
                return None

        if mode is AppMode.SIMULATION:
            return Session(mode, create_mock_stage())
        if mode is AppMode.CAMERA_ONLY:
            return Session(mode, None)

        QApplication.setOverrideCursor(Qt.WaitCursor)
        error: Optional[StageCommunicationError] = None
        stage = None
        try:
            stage = connect_real_stage(port=stage_port)
        except StageCommunicationError as exc:
            error = exc
        finally:
            QApplication.restoreOverrideCursor()

        if error is None:
            return Session(mode, stage)

        action = _ask_after_stage_failure(str(error))
        if action == "retry":
            continue
        if action == "change":
            mode = None
            continue
        return None
