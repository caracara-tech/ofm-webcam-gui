"""
The help texts of the interface, in one place.

Every control that needs an explanation has a `HelpTopic`. Its `HelpEntry` has:

* `summary` - one sentence. It is the control's own tooltip, so every control
  explains itself on hover in the same way.
* `title` and `details` - only for topics that get a "?" button next to them
  (see `ui/widgets/help.py`): the longer explanation, shown when hovering or
  clicking that button.

Pure data, no Qt: the widgets only look texts up by topic. To document a new
control: add a `HelpTopic` member, add its entry in `_ENTRIES`, and attach it in
the panel with `set_tip()` (tooltip only) or `add_help()` (tooltip + "?").

Texts are built on demand (not at import) so they follow the active language,
and values that live in the code (like the autofocus sweep sizes) are read from
their single source of truth instead of being written here a second time.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum, auto
from typing import Callable, Dict

from .autofocus import AutoFocusSettings
from .i18n import _


class HelpTopic(Enum):
    # Camera
    CAMERA_SECTION = auto()
    CAMERA_DEVICE = auto()
    CAMERA_REFRESH = auto()
    CAMERA_BACKEND = auto()
    CAMERA_RESOLUTION = auto()
    CAMERA_START = auto()
    # Snapshots & recording
    CAPTURE_SECTION = auto()
    CAPTURE_OUTPUT_FOLDER = auto()
    CAPTURE_BROWSE = auto()
    CAPTURE_OPEN_FOLDER = auto()
    CAPTURE_SNAPSHOT = auto()
    CAPTURE_RECORDING = auto()
    CAPTURE_TIMESTAMP = auto()
    # Stage
    STAGE_SECTION = auto()
    STAGE_JOG_XY = auto()
    STAGE_JOG_Z = auto()
    STAGE_XY_STEP = auto()
    STAGE_Z_STEP = auto()
    STAGE_SPEED = auto()
    STAGE_POSITION = auto()
    STAGE_AUTOFOCUS = auto()
    STAGE_AUTOFOCUS_AFTER_JOG = auto()
    # Display
    DISPLAY_SECTION = auto()
    DISPLAY_GRID = auto()
    DISPLAY_SCALE_BAR = auto()
    DISPLAY_SCALE_COLOR = auto()
    DISPLAY_ADVANCED = auto()
    DISPLAY_CALIBRATION = auto()
    # Log, window and state
    LOG_SAVE = auto()
    LOG_VIEW = auto()
    LOG_VIEWER_SAVE = auto()
    LOG_VIEWER_FOLDER = auto()
    CHANGE_MODE = auto()
    ABOUT = auto()
    LOCKED_DURING_AUTOFOCUS = auto()


@dataclass(frozen=True)
class HelpEntry:
    summary: str
    title: str = ""
    details: str = ""  # paragraphs separated by "\n"

    @property
    def has_details(self) -> bool:
        return bool(self.title or self.details)


def help_entry(topic: HelpTopic) -> HelpEntry:
    """The text for `topic`, in the active language."""
    return _ENTRIES[topic]()


def _autofocus_details() -> str:
    s = AutoFocusSettings()
    return _(
        "Moves Z up and down around the current position and scores the sharpness of the centre of the "
        "image at each stop. It first searches \u00b1{coarse_range_um:g} \u00b5m in {coarse_step_um:g} \u00b5m "
        "steps, widening the search (up to {max_coarse_passes} times) while the sharpest point is at the edge "
        "of the range, then refines it with \u00b1{fine_range_um:g} \u00b5m in {fine_step_um:g} \u00b5m steps.\n"
        "Needs the camera stream running and a sample with visible detail. While it runs, an AUTOFOCUS badge "
        "is shown on the preview, the camera controls are locked and the progress is written to the log."
    ).format(
        coarse_range_um=s.coarse_range_um, coarse_step_um=s.coarse_step_um,
        max_coarse_passes=s.max_coarse_passes, fine_range_um=s.fine_range_um, fine_step_um=s.fine_step_um,
    )


# Each entry is a function so the texts are translated when asked for, not at import.
_ENTRIES: Dict[HelpTopic, Callable[[], HelpEntry]] = {
    # ------------------------------------------------------------- camera --
    HelpTopic.CAMERA_SECTION: lambda: HelpEntry(
        _("Choose the camera and how it is read, then start the live preview."),
        _("Camera"),
        _("The device, backend and resolution are read when the stream starts: to change them, stop the "
          "stream and start it again."),
    ),
    HelpTopic.CAMERA_DEVICE: lambda: HelpEntry(
        _("Which connected camera to use. Press the refresh button after plugging one in."),
    ),
    HelpTopic.CAMERA_REFRESH: lambda: HelpEntry(_("Refresh camera list")),
    HelpTopic.CAMERA_BACKEND: lambda: HelpEntry(
        _("The system interface used to talk to the camera."),
        _("Camera backend"),
        _("Windows offers Media Foundation (MSMF, the default) and DirectShow (DSHOW, a fallback); Linux uses "
          "V4L2; macOS uses AVFoundation.\nIf a camera does not open or the picture looks wrong, try the "
          "other backend."),
    ),
    HelpTopic.CAMERA_RESOLUTION: lambda: HelpEntry(
        _("The frame size requested from the camera."),
        _("Resolution"),
        _("If the camera cannot provide it, the driver picks a nearby size. Lower resolutions give a higher "
          "frame rate and smaller files. Snapshots and recordings use the size of the frames actually received."),
    ),
    HelpTopic.CAMERA_START: lambda: HelpEntry(
        _("Start or stop the live preview from the selected camera. Stopping also ends a recording in progress."),
    ),
    # ------------------------------------------------ snapshots & recording --
    HelpTopic.CAPTURE_SECTION: lambda: HelpEntry(
        _("Save still images or video of the live preview."),
        _("Snapshots & Recording"),
        _("Files go to the output folder. Snapshots are named frame_YYYYMMDD_HHMMSS_mmm.png and recordings "
          "recording_YYYYMMDD_HHMMSS.mp4."),
    ),
    HelpTopic.CAPTURE_OUTPUT_FOLDER: lambda: HelpEntry(
        _("The folder where snapshots and recordings are saved."),
    ),
    HelpTopic.CAPTURE_BROWSE: lambda: HelpEntry(_("Choose another output folder.")),
    HelpTopic.CAPTURE_OPEN_FOLDER: lambda: HelpEntry(_("Open this folder in the file manager")),
    HelpTopic.CAPTURE_SNAPSHOT: lambda: HelpEntry(
        _("Save the current frame as a PNG image. The scale bar and timestamp are included if enabled."),
    ),
    HelpTopic.CAPTURE_RECORDING: lambda: HelpEntry(
        _("Record the live preview to an .mp4 video file."),
        _("Recording"),
        _("The video is written at a fixed 20 frames per second. The scale bar and timestamp are included if "
          "enabled; the grid and the REC / AUTOFOCUS badges are not.\nYou can keep recording while auto-focus "
          "runs. Stopping the stream also stops the recording."),
    ),
    HelpTopic.CAPTURE_TIMESTAMP: lambda: HelpEntry(
        _("Print the date and time on every frame."),
        _("Timestamp"),
        _("It is drawn on the preview, on snapshots and on recordings. Turn it off for clean images."),
    ),
    # -------------------------------------------------------------- stage --
    HelpTopic.STAGE_SECTION: lambda: HelpEntry(
        _("Move the microscope stage and focus."),
        _("Stage Control"),
        _("L and R move along X, U and D along Y, W and S along Z (focus). Distances are in micrometres (\u00b5m) "
          "and are converted to motor steps with the stage calibration.\nThe position shown is counted by the "
          "program from where it started; the stage has no position sensors, so it can drift if the motors "
          "skip steps."),
    ),
    HelpTopic.STAGE_JOG_XY: lambda: HelpEntry(
        _("Move one XY step: L and R along X, U and D along Y."),
    ),
    HelpTopic.STAGE_JOG_Z: lambda: HelpEntry(
        _("Move one Z step to change focus: W and S move in the + and - direction."),
    ),
    HelpTopic.STAGE_XY_STEP: lambda: HelpEntry(
        _("Distance moved by each X/Y button press."),
        _("XY step"),
        _("In micrometres (\u00b5m), converted to motor steps with the stage calibration."),
    ),
    HelpTopic.STAGE_Z_STEP: lambda: HelpEntry(
        _("Distance moved by each Z button press."),
        _("Z step"),
        _("Smaller steps give finer focus control; use auto-focus for large changes."),
    ),
    HelpTopic.STAGE_SPEED: lambda: HelpEntry(
        _("How fast the stage moves, in \u00b5m per second."),
        _("Speed"),
        _("The controller has a maximum step rate, so very high speeds are capped. Lower speeds are gentler "
          "and help avoid skipped steps."),
    ),
    HelpTopic.STAGE_POSITION: lambda: HelpEntry(
        _("Stage position in \u00b5m, counted from where the program started."),
    ),
    HelpTopic.STAGE_AUTOFOCUS: lambda: HelpEntry(
        _("Find the sharpest focus by sweeping the Z axis."),
        _("Auto-focus"),
        _autofocus_details(),
    ),
    HelpTopic.STAGE_AUTOFOCUS_AFTER_JOG: lambda: HelpEntry(
        _("Automatically re-runs the Z-sweep autofocus after every X/Y jog."),
        _("Auto-focus after each XY move"),
        _("Keeps the sample in focus while exploring, at the cost of waiting for a sweep after every move."),
    ),
    # ------------------------------------------------------------ display --
    HelpTopic.DISPLAY_SECTION: lambda: HelpEntry(
        _("Aids drawn over the live preview."),
        _("Display"),
        _("The grid is only shown on screen. The scale bar is also saved in snapshots and recordings."),
    ),
    HelpTopic.DISPLAY_GRID: lambda: HelpEntry(
        _("Draw an alignment grid over the preview; the spacing is in image pixels. It is never saved."),
    ),
    HelpTopic.DISPLAY_SCALE_BAR: lambda: HelpEntry(
        _("Draw a scale bar over the image. It reads in pixels unless a physical calibration is set."),
    ),
    HelpTopic.DISPLAY_SCALE_COLOR: lambda: HelpEntry(
        _("Choose white or black, whichever reads better on your sample."),
    ),
    HelpTopic.DISPLAY_ADVANCED: lambda: HelpEntry(_("Show or hide the physical calibration option.")),
    HelpTopic.DISPLAY_CALIBRATION: lambda: HelpEntry(
        _("Show the scale bar in micrometres instead of pixels."),
        _("Physical calibration"),
        _("Pixels alone say nothing about real size: you need a reference. Image a stage micrometer (a slide "
          "with a ruler), measure how many pixels a known distance covers and enter the \u00b5m per pixel.\n"
          "The value only holds for this objective and camera resolution: change either and measure again."),
    ),
    # ------------------------------------------------ log, window, states --
    HelpTopic.LOG_SAVE: lambda: HelpEntry(
        _("Write everything logged in this session to a file, starting from the beginning of the session"),
    ),
    HelpTopic.LOG_VIEW: lambda: HelpEntry(_("Show the log of this session in a window")),
    HelpTopic.LOG_VIEWER_SAVE: lambda: HelpEntry(
        _("Write the whole session log (all levels) to a file of your choice"),
    ),
    HelpTopic.LOG_VIEWER_FOLDER: lambda: HelpEntry(_("Open the log folder in the file manager")),
    HelpTopic.CHANGE_MODE: lambda: HelpEntry(
        _("Return to the start screen to pick another mode or language"),
    ),
    HelpTopic.ABOUT: lambda: HelpEntry(_("About this program and its license")),
    HelpTopic.LOCKED_DURING_AUTOFOCUS: lambda: HelpEntry(_("Unavailable while auto-focus is running")),
}
