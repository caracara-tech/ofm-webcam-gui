"""The three ways the application can be launched.

Pure data (no Qt): the startup dialog, the CLI and MainWindow all share it.
"""

from __future__ import annotations

from enum import Enum


class AppMode(str, Enum):
    CAMERA_STAGE = "camera-stage"
    CAMERA_ONLY = "camera"
    SIMULATION = "simulation"

    @property
    def label(self) -> str:
        return _LABELS[self]

    @property
    def description(self) -> str:
        return _DESCRIPTIONS[self]

    @property
    def has_stage(self) -> bool:
        """True if this mode drives a stage (real or mock) and therefore shows stage controls."""
        return self is not AppMode.CAMERA_ONLY

    @property
    def stage_is_real(self) -> bool:
        return self is AppMode.CAMERA_STAGE


_LABELS = {
    AppMode.CAMERA_STAGE: "Camera + Stage",
    AppMode.CAMERA_ONLY: "Camera only",
    AppMode.SIMULATION: "Simulation",
}

_DESCRIPTIONS = {
    AppMode.CAMERA_STAGE: "Full microscope: live camera and motorized stage control. "
                          "Requires the stage board to be connected.",
    AppMode.CAMERA_ONLY: "Device without motors: camera preview, snapshots and recording. "
                         "No stage controls.",
    AppMode.SIMULATION: "No hardware needed: full interface with a simulated stage "
                        "(nothing physical moves).",
}
