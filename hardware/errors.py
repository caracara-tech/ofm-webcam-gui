"""Exceptions raised by the hardware layer (no PyQt, no cv2)."""

from __future__ import annotations


class StageCommunicationError(RuntimeError):
    """The stage could not be reached, or stopped answering mid-operation.

    The message is written for the end user: it is shown verbatim in an
    error dialog, so it should say what failed and what to check.
    """
