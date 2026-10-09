"""QThread that serializes stage movement requests off the UI thread."""

from __future__ import annotations

from dataclasses import dataclass
from typing import List

from PyQt5.QtCore import QMutex, QThread, pyqtSignal

from core.types import Direction
from hardware.abstract import StageController


@dataclass
class _QueuedMovement:
    stage: StageController
    direction: Direction
    steps: int
    delay_per_step_s: float
    status_message: str


class StageMovementThread(QThread):
    """Handles stage movements in a background thread to avoid blocking the UI."""

    movement_complete = pyqtSignal(str, object)  # (status_message, Direction)
    movement_failed = pyqtSignal(str, object)  # (error_message, Direction)

    def __init__(self) -> None:
        super().__init__()
        self._queue: List[_QueuedMovement] = []
        self._mutex = QMutex()
        self._running = False

    def add_movement(self, stage: StageController, direction: Direction, steps: int, delay_per_step_s: float, status_message: str) -> None:
        self._mutex.lock()
        try:
            self._queue.append(_QueuedMovement(stage, direction, steps, delay_per_step_s, status_message))
        finally:
            self._mutex.unlock()

    def run(self) -> None:
        self._running = True
        while self._running:
            self._mutex.lock()
            item = self._queue.pop(0) if self._queue else None
            self._mutex.unlock()

            if item is None:
                self.msleep(10)
                continue

            try:
                item.stage.move_steps(item.direction, item.steps, item.delay_per_step_s)
                self.movement_complete.emit(item.status_message, item.direction)
            except Exception as e:
                self.movement_failed.emit(str(e), item.direction)

    def stop(self) -> None:
        self._running = False
        self.wait(2000)
