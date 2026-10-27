"""One way to describe the state of a device (stage today; others later).

Pure data, no Qt. The camera already reports "not detected" as a headline plus
a description in the image box; this gives the other devices the same shape,
so a device that is missing looks the same whatever the device or the OS:

    headline     what happened            "Stage not detected"
    description  what to try              "Check the USB cable ..."
    detail       the underlying error     "Could not connect to the Sangaboard on COM5 ..."
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class DeviceState(str, Enum):
    CONNECTING = "connecting"
    CONNECTED = "connected"
    NOT_DETECTED = "not_detected"  # could not be reached when connecting
    LOST = "lost"                  # was working, then stopped answering


@dataclass(frozen=True)
class DeviceStatus:
    state: DeviceState
    headline: str
    description: str = ""
    detail: str = ""

    @property
    def is_ok(self) -> bool:
        return self.state is DeviceState.CONNECTED

    @property
    def can_retry(self) -> bool:
        return self.state in (DeviceState.NOT_DETECTED, DeviceState.LOST)

    def text(self) -> str:
        """Everything, as paragraphs (what a panel shows)."""
        return "\n\n".join(part for part in (self.headline, self.description, self.detail) if part)

    def one_line(self) -> str:
        """Short form for a status bar: the headline and the first line of the explanation."""
        first = next((line for line in (self.detail or self.description).splitlines() if line.strip()), "")
        return f"{self.headline}: {first}" if first else self.headline
