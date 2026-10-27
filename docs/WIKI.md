# OFM Webcam Viewer - Developer Wiki

This is the deep-dive companion to the top-level [README](../README.md).
Read this if you're new to the codebase and want to understand *why* it's
built the way it is, not just how to run it.

## Contents

- [How to explore this codebase without getting lost](#how-to-explore-this-codebase-without-getting-lost)
- [Software engineering concepts used in this project](#software-engineering-concepts-used-in-this-project)
- [Key functions by module](#key-functions-by-module)

Related guides: [BUILDING.md](BUILDING.md) (executables and packaging),
[TRANSLATING.md](TRANSLATING.md) (interface languages) and the
[README](../README.md) (install and run).

---

## How to explore this codebase without getting lost

Don't start at `app.py` and read top to bottom, the code is organized in
**layers**, and the fastest way to get lost is to jump between them before
you understand the shape of any single one. Instead, go **bottom-up**, one
layer at a time, in this order:

### 1. `core/types.py`

This file defines the vocabulary everything else speaks: `Axis`,
`Direction`, `Position`, `AxisCalibration`, `Resolution`, `CameraBackend`,
`StageMotionSettings`. Nothing in here does anything, it's all data
shapes. Once you know what a `Position` or a `Direction` *is*, every other
file's function signatures become self-explanatory instead of mysterious.

### 2. Read `core/` in full before touching `hardware/` or `ui/`

`core/` has **zero PyQt or hardware imports**, every function is pure
input-in, output-out logic you can run in a plain Python REPL. You should check them
in this order:

1. `core/types.py` —> the shared vocabulary (above).
2. `core/platform_info.py` —> how the app decides it's on Windows vs. Linux.
3. `core/stage_motion.py` —> turns a jog button click into motor steps.
4. `core/autofocus.py` —> turns "click autofocus" into a search strategy.
5. `core/config.py` —> default ports, resolutions, backend lists.

### 3. `hardware/abstract.py`

Read the `StageController` abstract base class in `hardware/abstract.py`
to see the *contract* every stage backend promises to fulfill. Then read
**one** concrete implementation, `hardware/stage/mock.py` is the
shortest and has no real serial I/O to distract you, to see how that
contract gets fulfilled. You don't need to read `sangaboard.py`
in detail on a first pass; it follows the same shape.

Then read `hardware/stage/__init__.py`'s `create_stage()` and the connection
part of `ui/stage_module.py` (`start()`, `_begin_connect()`, `_set_status()`).
Together they answer "how does the app decide whether it's talking to
real hardware, a simulation, or no stage at all, and what happens when the
board isn't there?" (the user picks an `AppMode` at launch; nothing is
auto-detected or silently swapped, and a missing board is reported in the
status bar and the log, never decided by a dialog before the window exists).

### 4. Read `ui/threads/` before `ui/panels/` or `ui/main_window.py`

The three `QThread` subclasses (`camera_thread.py`, `stage_thread.py`,
`autofocus_thread.py`) are where the app actually *does* things,
capturing frames, moving the stage, sweeping for focus. Each is
self-contained and readable on its own. `autofocus_thread.py` is the
most involved file in the project; read `core/autofocus.py` (step 2)
immediately before it so the math is fresh.

### 5. `ui/panels/`

Each panel (`camera_panel.py`, `capture_panel.py`, `stage_panel.py`) is a
self-contained `QGroupBox` with its own widgets and signals. They don't
know about each other or about hardware, they just emit Qt signals when
the user does something (`jog_requested`, `start_clicked`, etc.).

### 6. `ui/main_window.py`

By now every piece it wires together is already familiar, so
`MainWindow` reads as "plumbing", connecting panel signals to thread
slots, rather than a wall of unfamiliar logic. This is intentional: a
thin `MainWindow` is a *goal* of the architecture, not an accident (see
[Composition over inheritance](#composition-over-inheritance-and-a-thin-mainwindow) below).

### If you just want to trace one feature end-to-end

Pick a single user action and follow it through every layer, this is
faster for building a mental model than reading files in isolation:

- **"What happens when I click a Z-jog button?"** →
  `ui/panels/stage_panel.py` (emits `jog_requested`) →
  `ui/stage_module.py::StageModule._on_jog_requested` →
  `core/stage_motion.py::plan_jog` (pure math) →
  `ui/threads/stage_thread.py::StageMovementThread.add_movement` →
  `hardware/stage/sangaboard.py::_move_steps_raw` (actual serial I/O).
- **"What happens when the stage board isn't plugged in?"** →
  `app.py::run_sessions` (opens the window; nothing hardware-related happens first) →
  `ui/main_window.py::MainWindow.__init__` (`create_stage()` builds an unconnected
  controller, `StageModule.start()` is called last) →
  `ui/threads/stage_connect_thread.py::StageConnectThread.run` (background
  `connect()`) → `hardware/stage/sangaboard.py::connect` (raises
  `StageCommunicationError` with the explanation) →
  `ui/stage_module.py::_on_connect_failed` → `_set_status()` →
  `ui/panels/stage_panel.py::show_status` (controls off, Retry button) plus the
  status-bar line and the log entry.
- **"What happens when I click Autofocus?"** →
  `ui/stage_module.py::StageModule._run_autofocus` →
  `ui/threads/autofocus_thread.py::AutoFocusThread.run` →
  `core/autofocus.py::plan_autofocus_sweep` / `focus_score` / `best_offset`
  (pure math) → back to the stage controller for the actual moves.

---

## Software engineering concepts used in this project

If you're newer to structuring a non-trivial GUI application, these are
the recurring ideas behind *why* the code is organized this way, not
just a project changelog.

### Layered architecture / dependency direction

The codebase is split into three layers, `core`, `hardware` and `ui`, with
a strict rule: **a layer may only import from layers below it.**
`core` imports nothing project-specific. `hardware` may import `core` (for
example `core.i18n`, so hardware error messages can be translated) but
never `ui`. `ui` may import both. This is why, for example, you can run
`plan_jog()` from `core/stage_motion.py` in a bare Python shell with no
GUI or serial port anywhere near your machine, it has nothing to import
that would require them.

Why this matters practically: it means the hardest-to-test parts of the
system (real motor moves, real camera frames, real Qt widgets) are kept
as thin as possible, and the parts with actual *decisions* in them (how
many steps for this jog? which offset had the best focus score?) are
pure functions you can unit test or experiment with directly. If your PC
lacks a webcam or a stage, or you're writing tests, you don't need to
mock out half a GUI framework to check that the math is right.

### The Hardware Abstraction Layer

`hardware/abstract.py` defines `StageController` as an abstract base
class: a contract of methods (`connect()`, `move_steps()`,
`get_position()`, ...) that any stage must support, without saying
*how*. `SangaboardStageController` and `MockStageController` each implement
that same contract differently: one talks real serial protocol to a
Sangaboard, the other just fakes it in memory.

The payoff: everything above `hardware/`, the jog logic, the autofocus
sweep and the UI, is written against `StageController`, never against a
specific brand of hardware. Swapping which stage you're driving, or
adding another kind, never requires touching `core/` or `ui/` at all.
This is the same idea as a device driver in an operating system, or
`Comparable`/interfaces in typed languages generally: **program to an
interface, not an implementation.**

### Explicit modes, optional stage module, no silent fallback

The user picks an `AppMode` at launch (`core/app_mode.py`): Automated
(camera + real stage), Manual (camera only), or Simulation. Simulation is
command-line only: `AppMode.offered_at_startup` keeps it out of the start
screen. `ui/startup.py::choose_mode()` only returns that choice; it touches no
hardware. `MainWindow` asks `hardware.stage.create_stage(mode, port)` for the
matching controller (a Sangaboard, a `MockStageController`, or `None`; always
*not yet connected*) and builds `StageModule` only if there is one, so manual
mode contains no stage code paths to guard.

### Logging: an always-on history with an optional file

`core/logging_setup.py` (no Qt) installs two always-on handlers on the root
logger at startup: a bounded in-memory `LogHistory` (what the viewer shows) and a
temporary file that holds the *whole* session (deleted at exit, including via
`atexit` after a crash). Saving a log is a separate sink that can be switched on
and off while the program runs: `start_saving()` *creates* the file with the
whole session copied from the temporary file and keeps streaming to it;
`stop_saving()` *deletes* it, while recording continues in the temporary file, so
saving again yields a complete file. `start_saving()` opens with mode `"x"` and
refuses a file that already exists, which is what makes deleting on stop safe.
Copy-and-attach happens while holding the temporary handler's lock, so no record
falls between the copy and the stream. One level (`--log-level`) governs console,
history, temp file and saved file.

The GUI side is split the same way as the rest of the project: `LogBar` only
emits signals (`save_toggled`, `view_requested`, ...); `MainWindow` receives the
`LogSession` by **injection** (created in `app.py`, passed to every window, so the
log and the file survive "Change mode / language...") and reacts;
`LogViewerDialog` subscribes to the history and shows new lines live. A log call
can come from any thread, so the viewer receives entries through a Qt signal
(queued to the GUI thread) rather than touching widgets from the logging thread.
`install_excepthook()` sends uncaught exceptions to the log, which matters for the
windowed Windows executable (it has no console).

The start screen is not only for launch: `MainWindow._change_mode()` shows it
over the running window, and if a mode is chosen it sets `next_mode` and
closes (releasing the camera and the stage port first). `app.run_sessions()`
loops, starting the next session, so switching mode or language never closes
the program. Cancelling keeps the current session; changing only the language
rebuilds the window in the same mode.

### Composition over inheritance, and a thin `MainWindow`

`MainWindow` doesn't contain the camera logic, the stage logic, or the
autofocus logic itself, it *owns instances* of `CameraPanel`,
`StagePanel`, `CameraThread`, `StageMovementThread`, `AutoFocusThread`,
and wires their Qt signals together. This is composition: build complex
behavior by plugging together small, focused objects, rather than by
piling more and more responsibility into one class through inheritance
or sheer accumulation. It's also why the "read `main_window.py` last"
advice above works, by the time you get there, every piece it composes
is already a known quantity.

### Threading model: background work never blocks the UI

Qt applications have exactly one thread allowed to touch widgets: the
main/GUI thread. Anything slow or blocking, reading camera frames in a
loop, opening the stage's serial port, waiting for a stage to finish moving,
running a multi-second autofocus sweep, is done on a `QThread` subclass instead, which
communicates results back to the GUI thread via **signals** (Qt's
built-in, thread-safe publish/subscribe mechanism) rather than by
touching widgets directly from a background thread (which would be
undefined behavior / worse, since Qt widgets aren't thread-safe). This
project has four: `CameraThread` (continuously grabs frames),
`StageConnectThread` (connects or reconnects the stage), `StageMovementThread`
(executes queued stage moves), and `AutoFocusThread` (runs a focus sweep). If the UI ever "freezes" while
something is happening, that's the sign a blocking call snuck onto the
main thread and needs moving into one of these.

One subtlety worth internalizing from this project's own history: a
`QThread` must not be destroyed by Python's garbage collector while its
underlying OS thread is still finishing up, or Qt aborts the process.
The safe pattern used throughout (`autofocus_thread.py`,
`stage_thread.py`, `stage_connect_thread.py`) is to connect the thread's own `finished` signal to
`deleteLater()`, and to `.wait()` for it before dropping the last
reference, never just set the variable to `None` and hope the timing
works out.

### Pure functions for anything that's "just math"

`core/stage_motion.py::plan_jog()` and everything in `core/autofocus.py`
are pure functions: given the same inputs, they always return the same
output, with no side effects (no hardware calls, no Qt, no I/O). This is
deliberate and is what makes step 2 of the [exploration guide](#2-read-core-in-full-before-touching-hardware-or-ui)
above possible, you can understand and verify the *decision-making*
logic of the app (how far to jog, which focus position won a sweep)
completely separately from the *mechanics* of carrying it out (spinning
a real motor). It also makes these functions trivially unit-testable
without mocks: no camera, no serial port, no `QApplication` required.

### Coarse-to-fine search (in `core/autofocus.py`)

The autofocus algorithm is a two-stage search, a pattern worth
recognizing outside this codebase too: a **coarse** stage takes big
steps over a wide range to find roughly the right neighborhood fast
(and keeps *expanding* that range if the best-scoring point keeps
landing at the edge of what it searched, a sign the true answer is
further out), followed by one **fine** stage that takes small steps
over a narrow range to nail down precision. Searching at fine resolution
over a wide range would be needlessly slow; searching at coarse
resolution everywhere would never be precise. Coarse-to-fine gets both
speed and precision by not paying for both at the same time.

### Calibration-driven physical units, not hardware-specific magic numbers

Sweep and jog distances are specified in **micrometres**
(`AutoFocusSettings.range_um`, `StageMotionSettings.xy_step_um`, etc.),
not in raw motor steps, and converted to steps only at the last possible
moment using each stage's own `AxisCalibration` (nanometres-per-step,
which differs between stages). This is why
the same `AutoFocusSettings()` defaults produce sensible, comparable
physical sweeps regardless of which stage is plugged in, the
alternative (hardcoding step counts) silently means something different
in real-world distance on every different piece of hardware.

---

## Key functions by module

### `core/types.py` - shared vocabulary

- **`Axis`** (`Enum`) —> `X` / `Y` / `Z`.
- **`Direction`** (`Enum`) —> one of `LEFT/RIGHT/UP/DOWN/FORWARD/BACKWARD`;
  each knows its own `.axis` (which `Axis` it moves) and `.sign` (+1/-1).
- **`Position`** (`NamedTuple`) —> an `(x, y, z)` triple. The unit is
  implied by how you obtained it (steps vs. nm vs. µm), never mix units
  without converting.
- **`AxisCalibration.nm_per_step(axis)`** —> how many nanometres one motor
  step covers on a given axis, for a specific stage.
- **`Resolution`**, **`CameraBackend`**, **`StageMotionSettings`** —>
  small typed value objects used throughout the UI and hardware layers.

### `core/platform_info.py` - OS-aware defaults, centralized

- **`detect_platform()`** —> returns `Platform.WINDOWS` / `.LINUX` / `.MACOS`.
- **`PlatformProfile`** / **`current_profile()`** —> the single source of
  truth for anything that differs by OS: default camera backend, default
  serial port, whether camera-name detection is available. Nothing else
  in the codebase should call `platform.system()` directly, if you find
  yourself wanting to, it probably belongs here instead.

### `core/logging_setup.py` - session logging (no Qt)

- **`configure_logging(level_name, default_dir, save, path) -> LogSession`** —>
  installs the handlers once at startup (history always, console only if a
  console exists, file if `save`). A log file that can't be opened is reported
  in the log and never stops the program.
- **`LogHistory`** (a `logging.Handler`) —> the last `HISTORY_LIMIT` formatted
  records; `entries()` snapshots them, `subscribe(listener)` returns the backlog
  and registers for new entries atomically (nothing missed or duplicated).
- **`LogSession`** —> `start_saving(path=None)` (creates the file with the whole
  session so far, then streams; raises `OSError`, e.g. if the file exists, and
  leaves the session unchanged), `stop_saving()` (deletes the file, keeps
  recording), `read_full_log()` (the whole session from the temporary file),
  `saving`, `file_path`, `last_path`, `folder`, `close()` (keeps a saved file,
  removes the temporary one).
- **`resolve_log_path(path, default_dir)`** —> pure: nothing → timestamped file in
  the default folder; a folder (existing, or text ending in a separator) →
  timestamped file inside it; otherwise the path as given. Takes the raw text on
  purpose: a `Path` has already lost the trailing separator.
- **`install_excepthook()`**, **`describe_environment()`** —> uncaught exceptions
  into the log; the environment line at the top of every log.

### `core/device_status.py` - how a device reports itself

- **`DeviceState`** —> `CONNECTING` / `CONNECTED` / `NOT_DETECTED` / `LOST`.
- **`DeviceStatus(state, headline, description, detail)`** —> `is_ok`,
  `can_retry`, `text()` (what a panel shows) and `one_line()` (status bar).

### `core/app_info.py` - the app's own facts

- **`APP_NAME`**, **`LICENSE_NAME`**, **`LICENSE_SPDX`**, **`LICENSE_URL`**,
  **`LICENSE_NOTICE`** (translatable).
- **`load_license_text()`** —> the full license, from the `LICENSE` file next to
  the code (source checkout and PyInstaller builds, where the spec bundles it) or
  else the installed package's metadata (pip); `None` if neither exists, and the
  About dialog then shows the license URL instead.

### `core/config.py` - defaults and option lists

- **`platform_backends()`** —> which OpenCV capture backends to offer, for
  the current OS. There is no automatic choice: the user picks one, and a
  backend that fails to open is reported, not silently replaced.
- **`default_backend_position()`** —> which backend the dropdown should
  pre-select (the platform profile's `default_backend`).
- **`default_stage_port()`** —> default
  serial port (`COM*` on Windows, `/dev/tty*` on Linux).
- **`DEFAULT_OUTPUT_DIR`**, **`DEFAULT_LOG_DIR`** —> where captures and session
  logs go: next to the code from a checkout, under the home folder otherwise.

### `core/stage_motion.py` - jog planning math

- **`plan_jog(direction, settings, calibration, ...) -> JogPlan`** —> pure
  function: given a jog direction and the current UI step-size/speed
  settings, computes exactly how many motor steps to take and the delay
  between them. No hardware or Qt involved, this is "decide what to do,"
  separate from "go do it."

### `core/autofocus.py` - the autofocus search, as pure math

- **`AutoFocusSettings`** —> all tunable parameters for a sweep, in
  physical units (µm): coarse/fine range and step size, how aggressively
  the coarse search expands (`coarse_growth`), how many coarse passes are
  allowed, and the scoring region (`roi_fraction`).
- **`plan_autofocus_sweep(range_um, step_um, nm_per_step) -> AutoFocusPlan`**
  —> converts a physical-unit sweep window into motor steps for one
  specific stage's calibration.
- **`crop_center(frame, fraction)`** —> returns a centered crop of a
  frame; used so the focus metric isn't diluted by background/vignetting
  outside the actual sample.
- **`focus_score(frame, roi_fraction) -> float`** —> the sharpness metric:
  variance of the Laplacian of a (cropped) frame. Higher = sharper.
- **`sweep_offsets(range_steps) -> List[int]`** —> the list of index
  positions a sweep visits, from `-range_steps` to `+range_steps`.
- **`best_offset(offsets, scores) -> int`** —> picks the highest-scoring
  offset; ties break toward the offset closest to center rather than
  arbitrarily, so a flat/no-signal sweep can't accidentally "commit" to
  a direction it has no real evidence for.
- **`has_weak_signal(scores, min_relative_spread) -> bool`** —> flags a
  sweep whose scores barely vary at all (still uniformly out of focus
  everywhere it looked), so the search knows to keep expanding rather
  than trust a meaningless tie.
- **`is_at_search_boundary(chosen, range_steps) -> bool`** —> flags a
  sweep whose winner sits at the very edge of the window it searched,
  meaning the true peak may lie further out in that direction.

### `core/overlays.py` - preview-overlay drawing (grid + scale bar)

Pure input-frame-in/output-frame-out functions, same style as
`core/autofocus.py` - no Qt, no hardware, just `cv2`/`numpy` array
operations, so the geometry is unit-testable without a running GUI.

The scale bar defaults to **pixel units** (e.g. `"100 px"`), fully
automatic and computed straight from the frame's own dimensions - no
calibration needed. It only switches to physical units (e.g. `"50 um"`)
if the caller supplies a calibrated `um_per_pixel` value; there's no way
to derive real-world size from pixel counts alone, so the automatic
default is honest about what it can and can't know.

- **`grid_line_positions(size_px, spacing_px) -> List[int]`** - the 1-D
  line positions for one axis of the alignment grid; pure geometry,
  separated from the actual `cv2.line()` calls so it can be tested alone.
- **`draw_grid(frame, spacing_px, color, thickness) -> np.ndarray`** -
  draws an evenly-spaced alignment grid over a frame, in place.
- **`nice_scale_bar_length_px(frame_width_px, target_fraction) -> int`**
  / **`nice_scale_bar_length_um(um_per_pixel, frame_width_px, target_fraction) -> float`**
  - pick a "nice" round length (1/2/5 x a power of ten, e.g. `50` rather
  than `43.7`) whose on-screen width is close to `target_fraction` of the
  frame width, for the pixel and physical scale bars respectively. Both
  share the `_nice_round_number()` rounding logic.
- **`draw_scale_bar(frame, um_per_pixel=None, ...) -> np.ndarray`** -
  draws the bar (with end ticks) and its text label in the frame's
  bottom-right corner. `um_per_pixel=None` (the default) draws the
  automatic pixel-count bar; a positive `um_per_pixel` draws a physical
  bar instead. Labels are ASCII (`"50 um"`, not a literal micro-sign)
  since OpenCV's built-in Hershey fonts don't reliably render non-ASCII
  glyphs.

### `core/scale_calibration.py` - optional physical scale override

- **`validate_um_per_pixel(value) -> float`** - validates a user-entered
  µm/pixel override value, raising `ValueError` on a non-positive input.
  This is *optional*: the scale bar's automatic default needs it not at
  all. It exists for someone who has an actual reference measurement
  (e.g. imaged a stage micrometer once) and wants the bar in real units.
  This setup's objective has no zoom and Z only refocuses by moving the
  sample, so if supplied, it's a single fixed constant - not a function
  of Z.

### `hardware/abstract.py` - the hardware contract

- **`StageController`** (ABC) —> the interface every stage backend must
  implement: `connect()`, `disconnect()`, `is_connected()`,
  `move_steps()`, `get_position()` / `get_position_nm()` /
  `get_position_um()`, unit-conversion helpers (`steps_to_nm`,
  `nm_to_steps`, `um_to_steps`), and the `_move_steps_raw()` primitive
  each backend must define.
- **`CameraController`** / **`SensorController`** (ABCs) —> parallel
  contracts for camera/sensor hardware (arm, exposure, gain, ROI, frame
  acquisition), used for non-webcam camera hardware if/when added.

### `hardware/stage/__init__.py` - stage factories

- **`create_stage(mode, port) -> Optional[StageController]`** —> what the app
  uses: the controller for an `AppMode`, built but *not connected* (`None` for
  manual mode). The single place a mode is mapped to hardware.
- **`create_real_stage(port, timeout)`** —> an unconnected Sangaboard controller.
  Its `connect()` tries the platform default port first, then an automatic port
  scan, and raises `StageCommunicationError` with a user-readable explanation on
  failure. Never falls back to simulation.
- **`connect_real_stage(port, timeout)`** —> create + connect in one blocking
  call, for scripts (the GUI does not use it: it would freeze the window).
- **`create_mock_stage() -> MockStageController`** —> the simulated stage,
  already connected.

### `core/i18n.py`, `ui/language.py`, `tools/i18n.py` - interface language

- **`core/i18n.py`** (stdlib `gettext` only, no Qt, no extra dependency):
  `_()`, `ngettext()`, `pgettext()`, `N_()` and `set_language()`. English
  source text is the message id, so missing translations fall back to
  English. Languages are discovered from `core/locales/*/LC_MESSAGES/*.mo`
  and carry their own name inside the catalog, so adding one needs no code.
- **`ui/language.py`** —> the Qt side: remembers the choice (QSettings) and
  switches Qt's built-in texts (OK/Cancel, file dialogs) to the same language.
- **`tools/i18n.py`** —> translator tooling (extract/update/new/compile/check),
  the only code that needs Babel. The app never imports it.
- The language is fixed for a run (chosen in the startup dialog or `--lang`),
  which lets the UI size itself once and avoids retranslating live widgets.
- Full workflow and style guide: [TRANSLATING.md](TRANSLATING.md).

### `ui/startup.py` and `ui/stage_module.py`

- **`ModeDialog` / `choose_mode()`** —> the mode (and language) picker; returns
  the mode, touches no hardware.
- **`StageModule`** —> owns the stage controller, `StageConnectThread`,
  `StageMovementThread`, position timer, `StagePanel`, and the jog/autofocus
  handlers. `start()` begins connecting; `retry_connection()` reconnects;
  `_set_status()` is the single place connection state changes;
  `_handle_stage_failure()` turns a mid-run failure into `LOST`. Not created in
  manual mode.

### `hardware/stage/{sangaboard,mock}.py` - concrete backends

Each implements the same `StageController` contract:

- **`connect()` / `disconnect()` / `is_connected()`** —> connection
  lifecycle.
- **`send_command(cmd)`** —> backend-specific wire protocol (serial text
  commands for Sangaboard; a no-op for the mock).
- **`_move_steps_raw(...)`** —> the actual step-issuing primitive; this is
  the one method that's genuinely different per backend (real serial
  writes vs. an in-memory position update).
- **`set_step_delay()`**, **`stop()`** —> speed control and emergency stop.

`_position_tracking.py::PositionTrackingMixin` supplies `get_position()` /
`set_position()` / `_apply_step_delta()` once, shared by all three
backends, instead of each reimplementing the same bookkeeping.

### `hardware/cameras.py` - which cameras exist

- **`list_cameras()`** —> returns a `CameraListing` of `CameraDevice(index,
  name)`, sorted by index, for the camera dropdown. Windows: DirectShow names
  through the optional `pygrabber` package (never imported elsewhere).
  Linux: read from `/sys/class/video4linux`, skipping the extra metadata
  nodes a camera exposes. If nothing can be listed, `note` says why and the
  UI falls back to generic "Camera N" entries.

### `ui/threads/camera_thread.py` - continuous frame capture

- **`CameraThread.run()`** —> opens the capture device and continuously
  reads frames in a loop, emitting each one via a Qt signal; this keeps
  the capture loop itself off the GUI thread.
- **`_open_capture()`** —> builds the `cv2.VideoCapture` with the chosen
  backend/resolution.
- **`error_occurred(kind, message)`** —> emitted when the camera can't be
  opened (`not_detected`), stops delivering frames (`lost`), or fails
  otherwise (`other`); `MainWindow._on_error()` turns the kind into the
  headline shown in the image box.
- **`stop()`** —> signals the loop to exit and releases the device.

### `ui/threads/stage_connect_thread.py` - connecting without freezing the window

- **`StageConnectThread(stage, reset=False)`** —> runs `stage.connect()` (after
  `disconnect()` when `reset=True`, i.e. a retry) and emits exactly one of
  `connected()` / `failed(message)`; `cancel()` releases the stage if the window
  closed meanwhile.

### `ui/threads/stage_thread.py` - queued stage moves

- **`StageMovementThread.add_movement(...)`** —> enqueues one move
  request (direction, steps, delay, status text) to be executed off the
  GUI thread.
- **`run()`** —> processes the queue, issuing moves via the connected
  `StageController` and reporting completion back via signals.
- **`movement_complete(message, direction)`** / **`movement_failed(message,
  direction)`** —> success vs. a `StageCommunicationError`; the latter makes
  `StageModule` show the error dialog and disable the stage controls.
- **`stop()`** —> drains/stops the queue cleanly.

### `ui/threads/autofocus_thread.py` - the autofocus sweep, run against real hardware

- **`AutoFocusThread.run()`** —> orchestrates the coarse-to-fine search
  described above: repeated coarse passes (expanding the search window
  on an edge-hit or a weak-signal result) followed by one fine pass,
  reporting progress and a final result message via signals. If the stage
  stops answering it emits `stage_failed` (handled like a failed jog) before
  the final message.
- **`_run_one_sweep(plan)`** —> executes one sweep (coarse or fine): moves
  to the start of the window, samples+scores a frame at each position,
  returns to the best-scoring one.
- **`_get_fresh_frame(settle_s)`** —> waits for a frame that was actually
  captured *after* the most recent move finished (using a frame counter),
  rather than blindly sleeping and risking a stale, pre-move frame.

### `ui/panels/*.py` - self-contained UI widgets

- **`CameraPanel`** —> camera dropdown (by name, with a refresh button),
  resolution and backend selection, Start/Stop; exposes `device_index`,
  `resolution`, `backend` and `refresh_devices()`.
- **`CapturePanel`** —> output folder row (path, Browse, Open folder),
  snapshot/recording buttons and the timestamp toggle under them; exposes
  `burn_timestamp`, `set_recording()`, `set_output_dir_text()`. Opening the
  folder goes through `ui/desktop.py::open_in_file_manager()`.
- **`StagePanel`** —> jog buttons, step/speed settings, live position
  readout, Autofocus button, plus a **Retry connection** button shown only while
  the stage is not detected or was lost (no text area: the reason goes to the
  status bar and the log); exposes
  `show_status(DeviceStatus)`, `update_position_display()`, `set_jog_enabled()`
  (blocks new moves while one is in flight), `set_enabled_all()`; emits
  `retry_requested`. The tooltip of the Retry button says what to check.
- **`LogBar`** —> **Save log to file** checkbox and **View log...** button, small
  enough for the status bar (the controls column is already screen-tall); emits
  `save_toggled`, `view_requested`; `set_saving()` reflects the real state without
  re-emitting.
- **`DisplayPanel`** - preview-overlay controls: grid toggle + spacing,
  scale bar toggle with a white/black colour choice, and a collapsed-by-default **Advanced** section
  holding an optional physical `um_per_pixel` override (`None` unless the
  user explicitly enables it). Like the other panels, it only collects
  input and exposes properties (`show_grid`, `show_scale_bar`,
  `scale_bar_color`, `um_per_pixel_override`); the actual drawing lives in
  `core/overlays.py`. The advanced section starts hidden via
  `self.advanced_frame.setVisible(False)`, toggled by a `QToolButton`
  rather than a full custom collapsible-group-box widget - simplest
  thing that reads clearly as "click to expand."

### `ui/dialogs/` - windows opened from the main window

- **`LogViewerDialog(history)`** —> non-modal live log: level filter,
  Save a copy... (the whole session, not just the lines in memory), Open folder; scrolls with new lines unless the user scrolled
  up. Subscribes to the `LogHistory` and unsubscribes
  when closed.
- **`AboutDialog`** —> name, version, license notice and the full license text.

### `ui/main_window.py` - composition root

Owns the panels and threads and wires them together via signals; doesn't
contain camera/stage/autofocus *logic* itself. Notable methods:

- **`__init__(mode, log_session, stage_port)`** -> the stage is created in
  `_build_ui()` and `StageModule.start()` is called last, once the window is wired.
- **`_build_ui()`** -> assembles panels into the main layout; the permanent
  **About / License (GPL-3.0)** button sits in the status bar.
- **`_on_save_log_toggled()` / `_show_log_viewer()` / `_open_log_folder()` /
  `_show_about()`** -> react to `LogBar` and the About button. The status-bar
  buttons are deliberately normal (not flat) buttons so they read as clickable,
  unlike the status message beside them. `_grow_to_fit()` re-fits the window when
  the Display panel's **Advanced** section expands (`adjustSize()` is capped at
  two thirds of the screen and a layout's minimum height ignores wrapped text).
- **`_start_stream()` / `_stop_stream()`** -> start/stop `CameraThread`.
- **`_on_frame(frame, fps)`** -> receives frames from `CameraThread`. Calls
  `_draw_overlays()` for whatever should be baked into the saved video
  (scale bar, timestamp) *before* writing to `VideoWriter`, then applies`
  preview-only extras, the alignment grid and the blinking "REC"
  indicator, to a separate copy used only for the on-screen `QPixmap`,
  so neither ends up in the saved file.
- **`_draw_overlays(frame)`** -> overlays that *are* meant to be part of
  the saved data: the scale bar (via `core/overlays.py::draw_scale_bar`,
  passed `DisplayPanel.um_per_pixel_override` - `None` unless the user
  turned on the Advanced override, in which case it's the physical bar
  instead of the automatic pixel one) and the burned-in timestamp. Used
  by both the recording path (in `_on_frame`) and snapshot saving, so a
  saved PNG and a saved video frame get identical treatment.
- **`_on_error(kind, message)`** —> camera failures are shown in the image
  box ("Camera not detected" / "Camera disconnected"), not in a modal.
- **`StageModule._on_jog_requested(direction)`** -> calls `plan_jog()`, then
  queues the move on `StageMovementThread`; `_run_autofocus()` constructs and
  starts an `AutoFocusThread`; `_on_autofocus_finished(message)` cleans the
  thread up safely (see
  [threading model](#threading-model-background-work-never-blocks-the-ui)).
- **`closeEvent()`** —> stops all threads and disconnects hardware before
  the window closes.

### `app.py` - entry point

- **`parse_args(argv)`** —> CLI flags: `--mode`, `--stage-port`, `--lang`,
  `--log-level`, `--save-log [PATH]` (`--simulate` kept as an alias).
- **`main()`** —> parses, sets up logging (before any heavy import, so start-up
  problems are logged too), then runs the app and always closes the log.
- **`run_sessions()`** —> picks the mode (`choose_mode()`), opens a `MainWindow`
  per session with the shared `LogSession`, loops on "Change mode / language...".
