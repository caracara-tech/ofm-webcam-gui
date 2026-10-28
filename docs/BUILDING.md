# Building and packaging

How to turn the project into a Windows executable, a Linux AppImage, a macOS
`.dmg`, or a pip-installable package. To just run the app from source, see the
[README](../README.md).

## Distributables

PyInstaller does not cross-compile: **build each artifact on its own OS** (the
GitHub Actions workflow `.github/workflows/build.yml` does exactly that on
version tags). All platforms share `packaging/ofm_webcam_gui.spec`. Every script
works from any folder, creates its own `venv`, and installs the platform
requirements plus PyInstaller.

| Platform | Command | Output |
|---|---|---|
| Windows | `packaging\build_windows.bat` | `dist\windows\ofm-webcam-gui.exe` |
| Linux (any distribution) | `./packaging/linux/build_appimage.sh` | `dist/linux/ofm-webcam-gui-<version>-<arch>.AppImage` |
| macOS | `./packaging/macos/build_dmg.sh` | `dist/macos/ofm-webcam-gui-<version>-<arch>.dmg` |

The Linux and macOS commands run their first step (`packaging/build_linux.sh`,
`packaging/build_macos.sh`: the PyInstaller build) on their own when needed. Each
build ends with a smoke test (`--help` without a display).

**Layering.** `ofm_webcam_gui.spec` decides *what is bundled* (one place for all
OSes); `build_<os>.sh` runs PyInstaller; `linux/build_appimage.sh` and
`macos/build_dmg.sh` only *wrap* that output in the platform's distribution
format; `lib/common.sh` holds what the scripts share (repo root, version read
from `core/version.py`). Adding a platform or format means adding one wrapper
script, not touching the others.

What the builds do differently from running from source:

- They contain everything, including the compiled translation catalogs, Qt's
  own Spanish texts and the `LICENSE` file (shown by **About / License**).
- They save captures to `~/Pictures/ofm-webcam-gui`, session logs to
  `~/ofm-webcam-gui/logs`, and remember the interface language per user.
- Windows is a single-file `.exe` (unpacks itself on every launch). Linux and
  macOS are folder builds inside the AppImage / `.app`, so they start faster.

## Troubleshooting a build

- **A language is missing from the built app.** The build packs the compiled
  `.mo` files that are committed. Run `python tools/i18n.py compile` after
  editing a `.po` file (see [TRANSLATING.md](TRANSLATING.md)).
- **The About dialog says the license file was not found.** The spec must bundle
  `LICENSE` (it does: the `datas.append(...)` line for it); if you changed the
  spec, keep that line.
- **Nothing visible when a windowed build crashes.** Uncaught exceptions are
  written to the session log: run with `--save-log` and read the file (or switch
  on **Save log to file** in the window), or use `console=True` as above.

## The Windows .exe

- **The Windows `.exe` fails silently.** It is built without a console window.
  Set `console=True` in `packaging/ofm_webcam_gui.spec`, rebuild, and run it from
  a terminal to see the traceback. (`--help` and argument errors open in a
  dialog instead of the console.)
- **Windows Defender flags a fresh `.exe`** the first time. This is common with
  single-file PyInstaller builds.

## The Linux AppImage

- **Run it:** `chmod +x ofm-webcam-gui-*.AppImage && ./ofm-webcam-gui-*.AppImage`.
  No installation, no root. Optional desktop integration with a tool such as
  AppImageLauncher.
- **Compatibility:** it runs on any distribution whose glibc is at least as new
  as the build machine's. Build on the **oldest** distribution you want to
  support (CI uses Ubuntu 22.04), never on a rolling release. Qt and OpenCV are
  bundled; the system must still provide the basic graphics libraries every
  desktop has (`libGL`, `libxkbcommon-x11`). If a very minimal system lacks them,
  install `libgl1` and `libxkbcommon-x11-0` (Debian/Ubuntu names).
- **FUSE:** AppImages normally need FUSE 2 to run. Without it, run with
  `APPIMAGE_EXTRACT_AND_RUN=1 ./ofm-webcam-gui-*.AppImage`.
- **Build tooling:** `desktop-file-validate` (package `desktop-file-utils`) and
  `curl`. `appimagetool` is downloaded once, pinned to a version and verified by
  SHA-256 (set `APPIMAGETOOL` to use your own copy). Architectures: x86_64 and
  aarch64, each built on a machine of that architecture.
- **Icon:** `packaging/assets/ofm-webcam-gui.png` is a **placeholder**; replace
  it with the real 256x256 (or larger) PNG. The macOS icon is generated from it.
- **Serial permissions** (`dialout` group) are the same as for a source install.

## The macOS app and .dmg

- **Build on a Mac.** The result matches the architecture of that Mac (Apple
  Silicon `arm64` or Intel `x86_64`); OpenCV publishes per-architecture wheels, so
  there is one `.dmg` per architecture. Requires Python 3.11+.
- **Camera permission:** the bundle declares `NSCameraUsageDescription`; macOS
  asks the user the first time the stream starts. Without that key the system
  kills the app on camera access.
- **Signing and notarization:** without a signing identity the app is unsigned
  for distribution, and Gatekeeper blocks the first launch ("cannot be opened").
  Users can approve it with right-click > Open (or System Settings > Privacy &
  Security > Open Anyway). To sign, set `CODESIGN_IDENTITY="Developer ID
  Application: ..."` when building; this needs a paid Apple Developer account.
  Notarization (`xcrun notarytool`) is not scripted yet.
- **Known gaps on macOS:** the camera dropdown shows generic entries (names are
  only listed on Windows and Linux), and the stage port is auto-scanned
  (`/dev/cu.usbmodem*` on a Mac).

## Installable package (`pip install .`)

```bash
pip install .          # or: pip install -e .  while developing
ofm-webcam-gui --help
```

This adds an `ofm-webcam-gui` command, with its dependencies taken from
`pyproject.toml`. A pip-installed copy saves captures to
`~/Pictures/ofm-webcam-gui` instead of the repository's `gallery/` folder.

## Things that live in one place

- **License:** the `LICENSE` file only. The PyInstaller spec bundles it, the
  AppImage build installs it under `usr/share/doc`, and `core/app_info.py::load_license_text()`
  reads it (from the code folder, or from the package metadata for pip installs).
- **Version:** `core/version.py` only. `pyproject.toml`, the window title, the
  packaging scripts and the translation tool all read it.
- **Dependencies:** listed twice, in `requirements/*.txt` (used for running from
  source and by the build scripts) and in `pyproject.toml` (used by
  `pip install .`). Keep the two in step when you add or change a dependency.
  `requirements/i18n.txt` is separate on purpose: it is only for translation
  work and is not part of either list.

## Before a release

```bash
pip install -r requirements/i18n.txt      # only if translations changed
python tools/i18n.py check --strict       # catalogs complete, compiled and consistent
```

Then run the build commands above.
