# OFM Webcam Viewer

[![Status](https://img.shields.io/badge/status-active-2E7D32)](../../)
[![Python](https://img.shields.io/badge/python-3.11%2B-1565C0)](../../)
[![PyQt5](https://img.shields.io/badge/UI-PyQt5-7B1FA2?logo=qt&logoColor=white)](../../)
[![OpenCV](https://img.shields.io/badge/vision-OpenCV-C62828?logo=opencv&logoColor=white)](../../)
[![Sangaboard](https://img.shields.io/badge/stage-Sangaboard-E65100)](../../)
[![Arduino](https://img.shields.io/badge/stage-Arduino-00838F?logo=arduino&logoColor=white)](../../)
[![Microscopy](https://img.shields.io/badge/application-Microscopy-F9A825)](../../)
[![License](https://img.shields.io/badge/license-GPL--3.0-5D4037)](LICENSE)

**Languages:** English | [Español](docs/es/README.es.md)

A PyQt5 + OpenCV application for streaming webcam feeds and capturing
snapshots/recordings, with optional precision XYZ stage control and
coarse-to-fine autofocus for microscopy setups (Sangaboard or Arduino-based
stages).

> **More documentation:** the [developer wiki](docs/WIKI.md) explains the
> architecture and every key function; [docs/BUILDING.md](docs/BUILDING.md)
> covers executables, the `.deb` and pip packaging;
> [docs/TRANSLATING.md](docs/TRANSLATING.md) covers interface languages.
> This README covers running the app.

---

## Project structure

```
ofm-webcam-gui/
├── app.py                      # Entry point: python app.py [--mode manual|automated|simulation] [--stage-port PORT] [--lang CODE] [--log-level DEBUG]
├── pyproject.toml              # Package metadata + dependencies (optional: pip install .)
├── requirements/               # Dependency lists per platform (base / windows / linux; i18n for translators)
├── core/                       # Framework-agnostic types, config, and math (no Qt, no cv2 I/O)
│   ├── types.py                #   Axis, Direction, Position, AxisCalibration, Resolution, ...
│   ├── version.py              #   The application version
│   ├── platform_info.py        #   Platform detection + per-OS defaults (PlatformProfile)
│   ├── app_mode.py             #   AppMode enum: manual / automated / simulation
│   ├── i18n.py                 #   Interface-language runtime
│   ├── locales/                #   Translation catalogs
│   ├── config.py               #   Resolutions, backend lists, default ports, default output folder
│   ├── stage_motion.py         #   plan_jog(), pure jog-planning math (unit-testable)
│   ├── autofocus.py            #   Autofocus search math: sweep planning, focus scoring, convergence
│   ├── overlays.py             #   draw_grid() / draw_scale_bar(), pure preview-overlay drawing
│   └── scale_calibration.py    #   validate_um_per_pixel(), optional physical override for the scale bar
├── hardware/                   # Hardware abstraction layer (no PyQt imports)
│   ├── abstract.py             #   StageController / CameraController / SensorController ABCs
│   ├── cameras.py              #   Lists connected cameras by name (Windows: pygrabber, Linux: sysfs)
│   ├── errors.py               #   StageCommunicationError
│   └── stage/
│       ├── __init__.py         #   connect_real_stage() (raises on failure) / create_mock_stage()
│       ├── arduino.py          #   ArduinoStageController
│       ├── sangaboard.py       #   SangaboardStageController
│       ├── mock.py             #   MockStageController (simulation)
│       └── _position_tracking.py  # Shared position-bookkeeping mixin
├── ui/                         # PyQt5 presentation layer
│   ├── startup.py              #   Launch flow: mode + language dialog, stage connection (Retry/Change/Quit)
│   ├── language.py             #   Applies and remembers the interface language (Qt side of core/i18n)
│   ├── main_window.py          #   QMainWindow: composes panels + threads, owns app state
│   ├── stage_module.py         #   StageModule: stage controller, thread, panel, jog/autofocus, failure handling
│   ├── panels/                 #   CameraPanel, CapturePanel, StagePanel, DisplayPanel (QGroupBox widgets)
│   └── threads/                #   CameraThread, StageMovementThread, AutoFocusThread (QThread)
├── packaging/                  # PyInstaller spec + build scripts (see docs/BUILDING.md)
├── tools/i18n.py               # Translation tooling (see docs/TRANSLATING.md)
└── docs/                       # WIKI.md (developers), BUILDING.md, TRANSLATING.md
```

**Dependency direction is one-way:** `ui` → `hardware`/`core`, `hardware` →
`core`. `core` and `hardware` have zero PyQt imports, so both layers can be
unit tested or reused headlessly. See [the wiki](docs/WIKI.md) for why this
matters and how to navigate it.

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

Without this, Automated mode cannot open the port and shows an explicit
error at startup (with a hint about this group); see
[Troubleshooting](#troubleshooting) below.

---

## Usage

```bash
python app.py                       # asks which mode to start in
python app.py --mode automated      # skip the dialog
python app.py --mode manual
python app.py --mode simulation     # command line only, not in the dialog
python app.py --stage-port COM5     # force the stage's serial port
python app.py --lang es_419         # interface language for this run (English, Spanish)
python app.py --log-level DEBUG
python app.py --help                # modes, features and examples
```

On launch you choose a mode in the start screen (or skip it with `--mode`):

| Mode | For | Stage controls | Behaviour |
|---|---|---|---|
| **Automated** | Full motorized microscope | Shown, real hardware | If the stage can't be reached at startup you get an error with *Retry / Choose another mode / Quit*. If it stops responding while running, an explicit error is shown and the stage controls are disabled. |
| **Manual** | Device without motors | Hidden | Camera selection, snapshots and recording only. |
| **Simulation** | Trying the software without hardware | Shown, simulated stage | Command line only (`--mode simulation` or `--simulate`); not listed in the start screen. Nothing physical moves; the window title ends in `SIMULATION`. |

To switch mode or language later, click **Change mode / language...** at the
top of the controls: it returns to the start screen without closing the
program. Cancel keeps the current session running. It is also the way to
reconnect after a stage error.

In every mode, if the camera can't be opened the image box says
**Camera not detected**; pick another device or backend from the dropdowns and
press Start Stream again.

### Controls

1. **Camera** —> pick the camera by name, the backend and the resolution, then
   Start Stream. The refresh button (↻) rereads the camera list after you plug
   one in.
2. **Snapshots & Recording** —> PNG snapshots or MP4 recording, saved to
   `gallery/` by default when running from the repository (`~/Pictures/ofm-webcam-gui`
   for the executables and pip installs). **Browse** picks another folder and
   **Open folder** shows the current one in your file manager so you can look
   through the saved files. The *Burn timestamp* option sits under the record
   button.
3. **Stage Control** —> U/D/L/R for XY (shown as Ar/Ab/Iz/De in Spanish), W/S for Z (focus); step sizes,
   speed, live position readout, and **Autofocus** (coarse-to-fine search
   around the current position, see [the wiki](docs/WIKI.md#coreautofocuspy--the-autofocus-search-as-pure-math)
   for how it works).
4. **Display** —> an alignment grid (preview only, never saved) and a
   scale bar (baked into snapshots/recordings, drawn in white or black, your
   choice). By default the scale bar
   reads in **pixels** (e.g. "100 px"), fully automatic, computed
   straight from the image, no setup required. An **Advanced** section
   (collapsed by default) lets you override it with a real physical
   µm/pixel value if you've calibrated your setup, see
   [Configuration](#configuration) below.

---

## Configuration

Stage port: Automated mode tries the platform default port first
(`DEFAULT_STAGE_PORT_WINDOWS` / `DEFAULT_STAGE_PORT_LINUX` in `core/config.py`),
then scans all serial ports. Force one with `--stage-port`, or pass `port=` to
`connect_real_stage()` / `SangaboardStageController()` in code. The Arduino
stage (`ArduinoStageController`) is implemented but not offered by the mode
dialog; to use it, construct it in place of the Sangaboard in
`connect_real_stage()` in `hardware/stage/__init__.py`.

Interface language: chosen in the startup dialog (remembered between runs) or
with `--lang`. To edit or add a language, see [docs/TRANSLATING.md](docs/TRANSLATING.md).

Autofocus tuning: `AutoFocusSettings()` in `StageModule._run_autofocus()`
(`ui/stage_module.py`); widen `coarse_range_um` or raise `max_coarse_passes`
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
- **Arduino stage** (alternative, code only): default port `COM12`. Requires
  `pyserial`. Not selectable from the mode dialog; see
  [Configuration](#configuration). Same `dialout` group requirement on Linux.
- **Camera names** in the device dropdown: on Windows they come from the
  `pygrabber` package (installed by `requirements/windows.txt`); on Linux they
  are read from the system, no extra package. Without names, the dropdown
  lists generic "Camera 0, 1, ..." entries.

---

## Troubleshooting

**Camera won't start** —> pick a different device in the list (↻ refreshes
it); switch backend from Media Foundation to DirectShow (Windows); check no
other app is using the camera; confirm drivers are installed.

**Stage not connecting on Linux (error at startup)** —>
almost always a `dialout` group / permissions issue; see
[Linux: USB serial permissions](#linux-usb-serial-permissions-dialout-group)
above. Also check `/dev/tty*` for the device, confirm `sangaboard` is
installed, and try `--stage-port /dev/ttyACM0`. The error dialog lists the
serial ports the computer can see.

**Stage not connecting (Windows)** —> find the board's `COM*` port in Device
Manager and pass it with `--stage-port COM5`; confirm `sangaboard` is
installed; close any other program that may hold the port.

**"Camera not detected" in the image box** —> pick another device or backend
and press Start Stream again; close other apps that use the camera.

**Interface stays in English** —> `python app.py --lang es_419`; the language
selector only appears in the startup dialog when a translation is installed.
If a language you added is missing, see [docs/TRANSLATING.md](docs/TRANSLATING.md).

**Autofocus doesn't reach true focus in one click** —> widen
`coarse_range_um` / raise `max_coarse_passes` in `AutoFocusSettings()` if
your typical starting offset is larger than the defaults search; if it
seems to stop early on genuinely blurry frames, tune
`has_weak_signal()`'s `min_relative_spread` in `core/autofocus.py`
against your camera's actual noise floor. See
[the wiki](docs/WIKI.md#coreautofocuspy--the-autofocus-search-as-pure-math)
for how the search works.

**Import errors** —> activate the virtualenv; `pip install -r requirements/<platform>.txt`;
confirm Python 3.11+.

---

## AI Usage Disclaimer

AI tools were used to assist with code generation, debugging, refactoring, and documentation. All code must be reviewed and validated regardless of its origin. This project follows a no-autonomous-AI-agents policy; AI agents may not independently modify or contribute code.

## License

See `LICENSE`. Provided as-is for laboratory and educational use.

## Contributors

- Joaquín Acosta Aguilera, Caracara Tech

- Pierre Padilla-Huamantinco, Caracara Tech