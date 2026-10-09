"""The ways the application can be launched.

Pure data (no Qt): the startup dialog, the CLI and MainWindow all share it.

- MANUAL     a device without motors: camera preview, snapshots, recording.
- AUTOMATED  the full microscope: camera plus a real motorized stage.
- SIMULATION a simulated stage, for trying the software without hardware.
             It is a command-line option only (`--mode simulation`) and is
             deliberately not offered in the startup dialog.
"""

from __future__ import annotations

from enum import Enum

from core.i18n import N_, _


class AppMode(str, Enum):
    MANUAL = "manual"
    AUTOMATED = "automated"
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
        return self is not AppMode.MANUAL

    @property
    def stage_is_real(self) -> bool:
        return self is AppMode.AUTOMATED

    @property
    def offered_at_startup(self) -> bool:
        """Whether the startup dialog lists this mode (simulation is command-line only)."""
        return self is not AppMode.SIMULATION


# Module-level tables are built at import time, before the language is
# chosen, so entries are only *marked* with N_ and translated on access.
_LABELS = {
    AppMode.AUTOMATED: N_("Automated"),
    AppMode.MANUAL: N_("Manual"),
    AppMode.SIMULATION: N_("Simulation"),
}

_DESCRIPTIONS = {
    AppMode.AUTOMATED: N_(
        "Full microscope: live camera and motorized stage control. "
        "Requires the stage board to be connected."
    ),
    AppMode.MANUAL: N_(
        "Device without motors: camera preview, snapshots and recording. "
        "No stage controls."
    ),
    AppMode.SIMULATION: N_(
        "No hardware needed: full interface with a simulated stage "
        "(nothing physical moves)."
    ),
}
