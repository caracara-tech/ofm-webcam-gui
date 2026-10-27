"""
Stage controller implementations, plus small factories so UI code doesn't have
to know about specific controller classes:

- `create_stage(mode, port)`  the one the application uses: the right controller
  for an `AppMode`, built but *not connected* (connecting is slow and can fail,
  so the UI does it in the background and reports the outcome).
- `create_real_stage()` / `create_mock_stage()`  the pieces behind it.
- `connect_real_stage()`  create + connect in one blocking call, for scripts that
  just want a working stage (raises on failure).
"""

from __future__ import annotations

import logging
from typing import Optional

from core.app_mode import AppMode
from hardware.abstract import StageController
from hardware.errors import StageCommunicationError

from .mock import MockStageController
from .sangaboard import SangaboardStageController

logger = logging.getLogger(__name__)

__all__ = [
    "MockStageController",
    "SangaboardStageController",
    "StageCommunicationError",
    "StageController",
    "connect_real_stage",
    "create_mock_stage",
    "create_real_stage",
    "create_stage",
]


def create_stage(mode: AppMode, port: Optional[str] = None) -> Optional[StageController]:
    """The stage controller for `mode`, not yet connected; None if the mode has no stage.

    This is the single place that maps a mode to hardware, so the rule
    "a mode has a stage exactly when `mode.has_stage`" cannot drift.
    """
    if not mode.has_stage:
        return None
    return create_real_stage(port=port) if mode.stage_is_real else MockStageController()


def create_real_stage(port: Optional[str] = None, timeout: float = 2) -> SangaboardStageController:
    """A Sangaboard stage controller, not yet connected.

    `connect()` on it raises StageCommunicationError (with a user-readable
    message) if the board cannot be reached. There is deliberately no silent
    fallback to simulation: the caller decides what to do about a failure.
    """
    return SangaboardStageController(port=port, timeout=timeout)


def create_mock_stage() -> MockStageController:
    """A simulated stage: always available, nothing physical moves."""
    controller = MockStageController()
    controller.connect()
    return controller


def connect_real_stage(port: Optional[str] = None, timeout: float = 2) -> SangaboardStageController:
    """Create and connect a real Sangaboard stage in one blocking call.

    Raises StageCommunicationError if it cannot be reached. The GUI does not use
    this (it would block the window); it connects in a background thread.
    """
    controller = create_real_stage(port=port, timeout=timeout)
    controller.connect()
    return controller
