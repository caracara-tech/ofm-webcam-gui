"""QThread that drives a Z-sweep autofocus routine.

Moves the stage through a range of Z offsets, scores the sharpness of the
live frame at each stop, then returns to whichever offset was sharpest.
Runs on a background thread for the same reason StageMovementThread does:
stage.move_steps() blocks, and we don't want that blocking the UI.
"""

from __future__ import annotations

from typing import Callable, Optional

import numpy as np
from PyQt5.QtCore import QThread, pyqtSignal

from core.autofocus import AutoFocusSettings, best_offset, focus_score, sweep_offsets
from core.types import Direction
from hardware.abstract import StageController


class AutoFocusThread(QThread):
    """Runs one autofocus sweep. `frame_getter` should return the most
    recent camera frame (or None if no frame is available yet) and must be
    safe to call from a non-UI thread - reading a plain attribute is fine."""

    progress = pyqtSignal(int, int)  # (current_step, total_steps)
    finished_focus = pyqtSignal(str)  # human-readable result/status message

    def __init__(
        self,
        stage: StageController,
        frame_getter: Callable[[], Optional[np.ndarray]],
        settings: AutoFocusSettings,
    ) -> None:
        super().__init__()
        self.stage = stage
        self.frame_getter = frame_getter
        self.settings = settings

    def run(self) -> None:
        s = self.settings
        offsets = sweep_offsets(s.range_steps)
        scores: list[float] = []

        try:
            if s.range_steps > 0:
                self.stage.move_steps(Direction.BACKWARD, s.range_steps * s.step_size, s.delay_per_step_s)

            for i, _offset in enumerate(offsets):
                self.msleep(max(1, int(s.settle_s * 1000)))
                frame = self.frame_getter()
                scores.append(focus_score(frame) if frame is not None else 0.0)
                self.progress.emit(i + 1, len(offsets))
                if i < len(offsets) - 1:
                    self.stage.move_steps(Direction.FORWARD, s.step_size, s.delay_per_step_s)

            chosen = best_offset(offsets, scores)
            steps_back = (offsets[-1] - chosen) * s.step_size
            if steps_back > 0:
                self.stage.move_steps(Direction.BACKWARD, steps_back, s.delay_per_step_s)

            best_score = scores[offsets.index(chosen)]
            self.finished_focus.emit(
                f"Auto-focus complete (sharpness {best_score:.1f}, offset {chosen:+d} steps from start)"
            )
        except Exception as e:
            self.finished_focus.emit(f"Auto-focus error: {e}")
