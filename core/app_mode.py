"""The three ways the application can be launched.

Pure data (no Qt): the startup dialog, the CLI and MainWindow all share it.
"""

from __future__ import annotations

from enum import Enum

from core.i18n import N_, _


class AppMode(str, Enum):
    CAMERA_STAGE = "camera-stage"
    CAMERA_ONLY = "camera"
    SIMULATION = "simulation"

    @property
    def label(self) -> str:
        return _(_LABELS[self])

    @property
    def description(self) -> str:
        return _(_DESCRIPTIONS[self])

    @property
    def has_stage(self) -> bool:
        """True if this mode drives a stage (real or mock) and therefore shows stage controls."""
        return self is not AppMode.CAMERA_ONLY

    @property
    def stage_is_real(self) -> bool:
        return self is AppMode.CAMERA_STAGE


# Module-level tables are built at import time, before the language is
# chosen, so entries are only *marked* with N_ and translated on access.
_LABELS = {
    AppMode.CAMERA_STAGE: N_("Camera + Stage"),
    AppMode.CAMERA_ONLY: N_("Camera only"),
    AppMode.SIMULATION: N_("Simulation"),
}

_DESCRIPTIONS = {
    AppMode.CAMERA_STAGE: N_(
        "Full microscope: live camera and motorized stage control. "
        "Requires the stage board to be connected."
    ),
    AppMode.CAMERA_ONLY: N_(
        "Device without motors: camera preview, snapshots and recording. "
        "No stage controls."
    ),
    AppMode.SIMULATION: N_(
        "No hardware needed: full interface with a simulated stage "
        "(nothing physical moves)."
    ),
}
