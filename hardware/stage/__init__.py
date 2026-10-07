"""
Stage controller implementations, plus two small factories so UI code
doesn't have to know about specific controller classes:
`connect_real_stage()` (raises on failure) and `create_mock_stage()`.
"""

from __future__ import annotations

import logging
from typing import Optional

from hardware.abstract import StageController
from hardware.errors import StageCommunicationError

from .arduino import ArduinoStageController
from .mock import MockStageController
from .sangaboard import SangaboardStageController

logger = logging.getLogger(__name__)

__all__ = [
    "ArduinoStageController",
    "MockStageController",
    "SangaboardStageController",
    "StageCommunicationError",
    "StageController",
    "connect_real_stage",
    "create_mock_stage",
]


def create_mock_stage() -> MockStageController:
    """A simulated stage: always available, nothing physical moves."""
    controller = MockStageController()
    controller.connect()
    return controller


def connect_real_stage(port: Optional[str] = None, timeout: float = 2) -> SangaboardStageController:
    """Connect to a real Sangaboard stage.

    Raises StageCommunicationError (with a user-readable message) if it
    cannot be reached. There is deliberately no silent fallback to
    simulation here: the caller decides what to do about a failure.
    """
    controller = SangaboardStageController(port=port, timeout=timeout)
    controller.connect()
    return controller
