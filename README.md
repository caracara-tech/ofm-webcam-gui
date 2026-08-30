# OFM Webcam Viewer

A PyQt5 + OpenCV application for streaming webcam feeds and capturing
snapshots/recordings, with optional precision XYZ stage control and
coarse-to-fine autofocus for microscopy setups (Sangaboard or Arduino-based
stages).

> **New to this codebase?** See the [developer wiki](docs/WIKI.md) for an
> architecture deep-dive, a suggested reading order, and documentation of
> every key function. This README covers running the app.

---

## Project structure

```
ofm-webcam-gui/
├── app.py                      # Entry point: python app.py [--simulate] [--log-level DEBUG]
├── core/                       # Framework-agnostic types, config, and math (no Qt, no cv2 I/O)
│   ├── types.py                #   Axis, Direction, Position, AxisCalibration, Resolution, ...
│   ├── platform_info.py        #   Platform detection + per-OS defaults (PlatformProfile)
│   ├── config.py               #   Resolutions, backend lists, default ports
│   ├── stage_motion.py         #   plan_jog(), pure jog-planning math (unit-testable)
│   ├── autofocus.py            #   Autofocus search math: sweep planning, focus scoring, convergence
│   ├── overlays.py             #   draw_grid() / draw_scale_bar(), pure preview-overlay drawing
│   └── scale_calibration.py    #   validate_um_per_pixel(), optional physical override for the scale bar
├── hardware/                   # Hardware abstraction layer (no PyQt imports)
│   ├── abstract.py             #   StageController / CameraController / SensorController ABCs
│   ├── camera_names.py         #   Windows-only (pygrabber) camera name detection
│   └── stage/
│       ├── __init__.py         #   create_stage_controller() factory (real hardware + fallback)
│       ├── arduino.py          #   ArduinoStageController
│       ├── sangaboard.py       #   SangaboardStageController
│       ├── mock.py             #   MockStageController (simulation)
│       └── _position_tracking.py  # Shared position-bookkeeping mixin
└── ui/                         # PyQt5 presentation layer
    ├── main_window.py          #   QMainWindow: composes panels + threads, owns app state
    ├── panels/                 #   CameraPanel, CapturePanel, StagePanel, DisplayPanel (QGroupBox widgets)
    └── threads/                #   CameraThread, StageMovementThread, AutoFocusThread (QThread)
```

**Dependency direction is one-way:** `ui` → `hardware`/`core`, `hardware` →
`core`. `core` and `hardware` have zero PyQt imports, so both layers can be
unit tested or reused headlessly. See [the wiki](docs/WIKI.md) for why this
matters and how to navigate it.

---

## Cross-platform support (Windows + Debian-based Linux)

All platform-specific decisions, default backend, default serial port,
whether camera-name detection is available, are resolved by
`core/platform_info.py` at runtime; nothing else in the codebase calls
`platform.system()` directly. `requirements/` is split into `base.txt`
(shared), `windows.txt` (adds `pygrabber` for camera-name detection), and
`linux.txt` (omits it, since it can't be installed on Linux).

---

## Installation (running from source)

```bash
python -m venv venv
source venv/bin/activate   # Windows: venv\Scripts\activate

# Windows:
pip install -r requirements/windows.txt
# Linux:
pip install -r requirements/linux.txt
```

### Linux: USB serial permissions (`dialout` group)

On Debian-based Linux, USB serial devices (Sangaboard, Arduino) show up as
`/dev/ttyACM*` or `/dev/ttyUSB*`, and by default only `root` and members
of the `dialout` group can read/write them. If the stage fails to connect
with a permissions error, add your user to that group:

```bash
sudo usermod -aG dialout $USER
```

**Log out and back in** (or reboot) for the new group membership to take
effect, it isn't picked up by an already-open terminal session. Verify
it worked with:

```bash
groups        # should list "dialout"
ls -l /dev/ttyACM0   # or whichever port your stage is on
```

Without this, `create_stage_controller()` will fail to connect and the
app will silently fall back to simulation mode rather than crash, see
[Troubleshooting](#troubleshooting) below if that happens unexpectedly.

---

## Usage

```bash
python app.py
python app.py --simulate        # no stage hardware required
python app.py --log-level DEBUG
```

Simulation mode is used automatically if no Sangaboard is detected on the
configured port, and can also be forced with `--simulate`.

### Controls

1. **Camera** —> pick device index, backend, resolution, then Start Stream.
2. **Snapshots & Recording** —> PNG snapshots or MP4 recording, saved to
   `gallery/` by default (configurable via Browse).
3. **Stage Control** —> U/D/L/R for XY, W/S for Z (focus); step sizes,
   speed, live position readout, and **Autofocus** (coarse-to-fine search
   around the current position, see [the wiki](docs/WIKI.md#core-autofocuspy--the-autofocus-search-as-pure-math)
   for how it works).
4. **Display** —> an alignment grid (preview only, never saved) and a
   scale bar (baked into snapshots/recordings). By default the scale bar
   reads in **pixels** (e.g. "100 px"), fully automatic, computed
   straight from the image, no setup required. An **Advanced** section
   (collapsed by default) lets you override it with a real physical
   µm/pixel value if you've calibrated your setup, see
   [Configuration](#configuration) below.

---

## Configuration

Default stage port: edit `DEFAULT_STAGE_PORT_WINDOWS` /
`DEFAULT_STAGE_PORT_LINUX` in `core/config.py`, or pass `port=` to
`create_stage_controller()` / `SangaboardStageController()` directly. To use
the Arduino-based stage instead of Sangaboard, construct an
`ArduinoStageController` in place of the call in `hardware/stage/__init__.py`.

Autofocus tuning: `AutoFocusSettings()` in `ui/main_window.py`'s
`_run_autofocus()`, widen `coarse_range_um` or raise `max_coarse_passes`
if your setup regularly needs to search further than the defaults reach;
tighten `fine_range_um`/`fine_step_um` for more precision at the cost of
sweep time.

Scale bar: the default pixel-count scale bar needs no setup. If you want
real physical units instead, open the Display panel's **Advanced**
section, check "Override with physical calibration", and enter a
**µm/pixel** value. Leave the override off if you don't have
a reference yet; the automatic pixel-count bar is still useful for
framing and relative comparisons.

---

## Hardware requirements

- **Sangaboard** controller via USB (default `COM5` on Windows, `/dev/ttyACM0`
  on Linux). Requires the `sangaboard` package. On Linux, requires the user
  to be in the `dialout` group (see above).
- **Arduino stage** (alternative): default port `COM12`. Requires `pyserial`.
  Same `dialout` group requirement on Linux.
- **Camera name detection** (Windows only, optional): `pip install pygrabber`,
  then use the "Detect Camera Names" button.

---

## Troubleshooting

**Camera won't start** —> try a different device index; switch backend from
Media Foundation to DirectShow (Windows); check no other app is using the
camera; confirm drivers are installed.

**Stage not connecting / silently running in simulation mode on Linux** —>
almost always a `dialout` group / permissions issue; see
[Linux: USB serial permissions](#linux-usb-serial-permissions-dialout-group)
above. Also verify the Sangaboard is on the configured port; check
`/dev/tty*` for the device; confirm `sangaboard` is installed; increase the
connect timeout.

**Stage not connecting (Windows)** —> verify the Sangaboard is on the
configured `COM*` port via Device Manager; confirm `sangaboard` is
installed; increase the connect timeout.

**Autofocus doesn't reach true focus in one click** —> widen
`coarse_range_um` / raise `max_coarse_passes` in `AutoFocusSettings()` if
your typical starting offset is larger than the defaults search; if it
seems to stop early on genuinely blurry frames, tune
`has_weak_signal()`'s `min_relative_spread` in `core/autofocus.py`
against your camera's actual noise floor. See
[the wiki](docs/WIKI.md#core-autofocuspy--the-autofocus-search-as-pure-math)
for how the search works.

**Import errors** —> activate the virtualenv; `pip install -r requirements/<platform>.txt`;
confirm Python 3.11+.

---

## License

See `LICENSE`. Provided as-is for laboratory and educational use.

## Contributors

- Joaquín Acosta Aguilera, Caracara Tech

- Pierre Padilla-Huamantinco, Caracara Tech