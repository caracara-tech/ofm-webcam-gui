"""
Stage controller implementations, plus a factory that encapsulates the
"try real hardware, fall back to simulation" policy so UI code doesn't
have to know about specific controller classes.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Optional

from hardware.abstract import StageController

from .arduino import ArduinoStageController
from .mock import MockStageController
from .sangaboard import SangaboardStageController

logger = logging.getLogger(__name__)

__all__ = [
    "ArduinoStageController",
    "MockStageController",
    "SangaboardStageController",
    "StageController",
    "StageInitResult",
    "create_stage_controller",
]


@dataclass
class StageInitResult:
    controller: StageController
    simulation_mode: bool
    simulation_reason: Optional[str]  # "user requested" | "not detected" | None


def create_stage_controller(*, simulate: bool, port: Optional[str] = None, timeout: float = 2) -> StageInitResult:
    """Create and connect a stage controller.

    If `simulate` is True, always returns a MockStageController.
    Otherwise, tries a SangaboardStageController and transparently falls
    back to simulation if it can't connect.
    """
    if simulate:
        logger.info("Starting in SIMULATION mode (user requested)")
        controller = MockStageController()
        controller.connect()
        return StageInitResult(controller, simulation_mode=True, simulation_reason="user requested")

    try:
        controller: StageController = SangaboardStageController(port=port, timeout=timeout)
        controller.connect()
        if not controller.is_connected():
            raise RuntimeError("Connection failed")
        return StageInitResult(controller, simulation_mode=False, simulation_reason=None)
    except Exception as e:
        logger.warning("Could not connect to stage: %s. Falling back to SIMULATION mode.", e)
        mock = MockStageController()
        mock.connect()
        return StageInitResult(mock, simulation_mode=True, simulation_reason="not detected")
