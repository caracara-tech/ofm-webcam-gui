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

from core.autofocus import (
    AutoFocusPlan,
    AutoFocusSettings,
    best_offset,
    focus_score,
    has_weak_signal,
    is_at_search_boundary,
    plan_autofocus_sweep,
    sweep_offsets,
)
from core.types import Axis, Direction
from hardware.abstract import StageController
from core.i18n import _, ngettext
from hardware.errors import StageCommunicationError


class AutoFocusThread(QThread):
    """Runs a coarse-to-fine autofocus search. `frame_getter` should return
    the most recent camera frame (or None if no frame is available yet)
    and must be safe to call from a non-UI thread - reading a plain
    attribute is fine.

    `frame_id_getter`, if given, should return a monotonically increasing
    counter that ticks up every time a new frame arrives (e.g. a frame
    count). It's used to wait for a frame that was actually captured
    *after* a move finished, rather than blindly sleeping for `settle_s`
    and hoping the camera pipeline caught up - a fixed sleep that's a
    little too short will silently score a stale, pre-move frame at every
    position, which smears out the true focus peak and makes the sweep
    converge on a blurrier, less accurate position."""

    progress = pyqtSignal(int, int)  # (current_step, total_steps)
    finished_focus = pyqtSignal(str)  # human-readable result/status message
    stage_failed = pyqtSignal(str)  # emitted (before finished_focus) if the stage stops responding

    def __init__(
        self,
        stage: StageController,
        frame_getter: Callable[[], Optional[np.ndarray]],
        settings: AutoFocusSettings,
        frame_id_getter: Optional[Callable[[], int]] = None,
    ) -> None:
        super().__init__()
        self.stage = stage
        self.frame_getter = frame_getter
        self.settings = settings
        self.frame_id_getter = frame_id_getter

    def _get_fresh_frame(self, settle_s: float) -> Optional[np.ndarray]:
        """Return a frame captured after this call started, waiting up to
        `settle_s` for a new one to arrive. Falls back to a plain timed
        sleep if no frame-id getter was supplied."""
        if self.frame_id_getter is None:
            self.msleep(max(1, int(settle_s * 1000)))
            return self.frame_getter()

        start_id = self.frame_id_getter()
        deadline_ms = max(1, int(settle_s * 1000))
        poll_ms = 5
        waited_ms = 0
        while waited_ms < deadline_ms:
            self.msleep(poll_ms)
            waited_ms += poll_ms
            if self.frame_id_getter() != start_id:
                break  # a genuinely new frame has arrived
        return self.frame_getter()

    def _run_one_sweep(self, plan: AutoFocusPlan) -> tuple[int, float, list[float]]:
        """Sweep `plan`'s window around the stage's *current* position,
        leave the stage parked at whichever offset scored best, and return
        (chosen_offset, best_score, all_scores). Runs entirely relative to
        wherever the stage already is, so passes can be chained/re-centered
        freely. `all_scores` is returned too so the caller can tell a real
        peak apart from a flat, no-signal sweep (see `has_weak_signal`)."""
        s = self.settings
        offsets = sweep_offsets(plan.range_steps)
        scores: list[float] = []

        if plan.range_steps > 0:
            self.stage.move_steps(
                Direction.BACKWARD, plan.range_steps * plan.step_size, s.delay_per_step_s,
            )

        for i, _offset in enumerate(offsets):
            frame = self._get_fresh_frame(s.settle_s)
            scores.append(focus_score(frame, s.roi_fraction) if frame is not None else 0.0)
            self.progress.emit(i + 1, len(offsets))
            if i < len(offsets) - 1:
                self.stage.move_steps(Direction.FORWARD, plan.step_size, s.delay_per_step_s)

        chosen = best_offset(offsets, scores)
        best_score = scores[offsets.index(chosen)]
        steps_back = (offsets[-1] - chosen) * plan.step_size
        if steps_back > 0:
            self.stage.move_steps(Direction.BACKWARD, steps_back, s.delay_per_step_s)
        return chosen, best_score, scores

    def run(self) -> None:
        s = self.settings
        nm_per_step = self.stage.calibration.nm_per_step(Axis.Z)

        try:
            # --- Stage 1: coarse search --------------------------------
            # Wide window, coarse steps: find the general region the true
            # focus lies in. Keep expanding the window and sweeping again
            # from the new (already re-centered) position as long as
            # either (a) the winner is stuck at the edge of the window -
            # the true peak is probably further out that way - or (b) the
            # whole window came back with no real signal at all (uniformly
            # out of focus), in which case the "winner" isn't meaningful
            # evidence of a direction and shouldn't be trusted either.
            coarse_range_um = s.coarse_range_um
            best_score = 0.0
            coarse_passes = 0
            keep_expanding = True

            while keep_expanding and coarse_passes < max(1, s.max_coarse_passes):
                coarse_passes += 1
                plan = plan_autofocus_sweep(coarse_range_um, s.coarse_step_um, nm_per_step)
                chosen, best_score, scores = self._run_one_sweep(plan)
                keep_expanding = (
                    is_at_search_boundary(chosen, plan.range_steps) or has_weak_signal(scores)
                )
                if keep_expanding:
                    coarse_range_um *= s.coarse_growth

            # --- Stage 2: fine search -----------------------------------
            # Now that we're in the right neighbourhood, one narrow,
            # finely-sampled sweep to nail down the actual peak to
            # sub-coarse-step precision.
            fine_plan = plan_autofocus_sweep(s.fine_range_um, s.fine_step_um, nm_per_step)
            _fine_chosen, fine_score, _fine_scores = self._run_one_sweep(fine_plan)
            best_score = max(best_score, fine_score)

            self.finished_focus.emit(
                ngettext(
                    "Auto-focus complete (sharpness {sharpness:.1f}, {passes} coarse pass + fine pass)",
                    "Auto-focus complete (sharpness {sharpness:.1f}, {passes} coarse passes + fine pass)",
                    coarse_passes,
                ).format(sharpness=best_score, passes=coarse_passes)
            )
        except StageCommunicationError as e:
            self.stage_failed.emit(str(e))
            self.finished_focus.emit(_("Auto-focus aborted: lost communication with the stage"))
        except Exception as e:
            self.finished_focus.emit(_("Auto-focus error: {error}").format(error=e))
