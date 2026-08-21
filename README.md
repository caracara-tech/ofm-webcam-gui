# OFM Webcam Viewer

A PyQt5 + OpenCV application for streaming webcam feeds and capturing
snapshots/recordings, with optional stage control for precision microscopy
setups (Sangaboard or Arduino-based stages).

## Project structure

```
ofm_webcam_gui/
├── app.py                     # Entry point (python -m ofm_webcam_gui.app)
├── core/                      # Framework-agnostic types & config (no Qt, no cv2 I/O)
│   ├── types.py               #   Axis, Direction, Position, Resolution, ...
│   ├── config.py               #   resolutions, backends, default ports
│   └── stage_motion.py         #   pure jog-planning math (unit-testable)
├── hardware/                  # Hardware abstraction layer (no PyQt imports)
│   ├── abstract.py             #   StageController / CameraController / SensorController ABCs
│   └── stage/
│       ├── arduino.py          #   ArduinoStageController
│       ├── sangaboard.py       #   SangaboardStageController
│       ├── mock.py             #   MockStageController (simulation)
│       └── __init__.py         #   create_stage_controller() factory (handles fallback)
└── ui/                        # PyQt5 presentation layer
    ├── main_window.py          #   QMainWindow: composes panels + threads
    ├── panels/                 #   CameraPanel, CapturePanel, StagePanel (QGroupBox widgets)
    └── threads/                #   CameraThread, StageMovementThread (QThread)
```

**Dependency direction is one-way:** `ui` → `hardware`/`core`, `hardware` → `core`.
`core` and `hardware` have zero PyQt imports, so the hardware layer (and the
jog-planning math in particular) can be unit tested or reused headlessly.

### What changed vs. the original single-file version

- Split the ~680-line `webcam_viewer.py` into UI panels (`ui/panels/`),
  background threads (`ui/threads/`), and a thin `MainWindow` that just wires
  them together.
- Stage backends live one-per-file under `hardware/stage/`, sharing position
  tracking via a small mixin (`_position_tracking.py`) instead of duplicating
  the same `set_position`/step-delta logic three times.
- `Direction` is now a proper `Enum` (was raw `'L'/'R'/'U'/'D'/'W'/'S'` strings
  threaded through the codebase) and carries its own `axis`/`sign`.
- The "connect to real hardware, fall back to simulation" logic that used to
  live inline in `MainWindow.__init__` is now `hardware.stage.create_stage_controller()`,
  independently testable and reusable.
- Restored `move_steps()` as a concrete method on the `StageController` base
  class — it was called throughout the original code but only the private
  `_move_steps_raw` primitive was ever defined.
- Speed→step-delay math was duplicated UI logic; it's now `core.stage_motion.plan_jog()`,
  a pure function with no Qt or hardware dependency.
- Added type hints throughout (`Position`, `AxisCalibration`, `Resolution`,
  `CameraBackend`, etc. as dataclasses/NamedTuples instead of bare tuples/strings).

## Cross-platform support (Windows + Debian-based Linux)

All platform-specific decisions — default backend, default serial port,
whether camera-name detection is available — are resolved by
`core/platform_info.py` at **runtime**, not by maintaining separate code
branches. Nothing else in the codebase calls `platform.system()` directly:

- `core/platform_info.py` — detects `Platform.WINDOWS` / `.LINUX` / `.MACOS`
  and exposes a `PlatformProfile` (default backend index, default stage
  port, `supports_camera_name_detection`).
- `hardware/camera_names.py` — the Windows-only (`pygrabber`/DirectShow)
  camera-name feature. On Linux it returns `supported=False` without ever
  importing `pygrabber`, so that dependency doesn't need to exist there.
- `requirements/` — split into `base.txt` (shared), `windows.txt` (adds
  `pygrabber`), and `linux.txt` (omits it — it can't be installed on Linux).
- `hardware/stage/arduino.py` / `sangaboard.py` default to `COM*` ports on
  Windows and `/dev/tty*` on Linux via the same profile.

## Installation (running from source)

```bash
python -m venv venv
source venv/bin/activate   # Windows: venv\Scripts\activate

# Windows:
pip install -r ofm_webcam_gui/requirements/windows.txt
# Linux:
pip install -r ofm_webcam_gui/requirements/linux.txt
```

## Usage

```bash
python -m app.py
python -m app.py --simulate        # no stage hardware required
python -m app.py --log-level DEBUG
```

Simulation mode is used automatically if no Sangaboard is detected on the
configured port, and can also be forced with `--simulate`.

### Controls

1. **Camera** — pick device index, backend, resolution, then Start Stream.
2. **Snapshots & Recording** — PNG snapshots or MP4 recording, saved to
   `gallery/` by default (configurable via Browse).
3. **Stage Control** — U/D/L/R for XY, W/S for Z (focus); step sizes, speed,
   live position readout, and optional Auto-Level Z.

## Configuration

Default stage port: edit `DEFAULT_STAGE_PORT_WINDOWS` /
`DEFAULT_STAGE_PORT_LINUX` in `core/config.py`, or pass `port=` to
`create_stage_controller()` / `SangaboardStageController()` directly. To use
the Arduino-based stage instead of Sangaboard, construct an
`ArduinoStageController` in place of the call in `hardware/stage/__init__.py`.

## Hardware requirements

- **Sangaboard** controller via USB (default `COM5` on Windows, `/dev/ttyACM0`
  on Linux). Requires the `sangaboard` package.
- **Arduino stage** (alternative): default port `COM12`. Requires `pyserial`.
- **Camera name detection** (Windows only, optional): `pip install pygrabber`,
  then use the "Detect Camera Names" button.

## Troubleshooting

**Camera won't start** — try a different device index; switch backend from
Media Foundation to DirectShow (Windows); check no other app is using the
camera; confirm drivers are installed.

**Stage not connecting** — verify the Sangaboard is on the configured port;
check Device Manager (Windows) / `/dev/tty*` (Linux); confirm `sangaboard` is
installed; increase the connect timeout.

**Import errors** — activate the virtualenv; `pip install -r requirements.txt`;
confirm Python 3.7+.

## License

See `LICENSE`. Provided as-is for laboratory and educational use.

## Contributors

Pierre Padilla-Huamantinco, Caracara Tech
