# Building and packaging

How to turn the project into a standalone Windows executable, a Linux binary,
a Debian package, or a pip-installable package. To just run the app from
source, see the [README](../README.md).

## Standalone executables

PyInstaller does not cross-compile: build the Windows `.exe` on Windows and the
Linux binary on Linux. Both use the same `packaging/ofm_webcam_gui.spec`. Run
from any folder (the scripts switch to the repository root themselves); each
script creates its own `venv`, installs the platform requirements plus
PyInstaller, and builds a single-file executable.

| Platform | Command | Output |
|---|---|---|
| Windows | `packaging\build_windows.bat` | `dist\windows\ofm-webcam-gui.exe` |
| Linux (Debian-based) | `./packaging/build_linux.sh` | `dist/linux/ofm-webcam-gui` |
| Linux `.deb` (after the line above) | `./packaging/linux/build_deb.sh` | `dist/linux/ofm-webcam-gui_<version>_amd64.deb` |

Install the `.deb` with `sudo apt install ./dist/linux/ofm-webcam-gui_<version>_amd64.deb`;
it adds an application-menu entry.

What the executables do differently from running from source:

- They contain everything, including the compiled translation catalogs, Qt's
  own Spanish texts and the `LICENSE` file (shown by **About / License**).
- They save captures to `~/Pictures/ofm-webcam-gui`, session logs to
  `~/ofm-webcam-gui/logs`, and remember the interface language per user.
- Startup is slow-ish: a single-file build unpacks itself on every launch.

## Troubleshooting a build

- **The Windows `.exe` fails silently.** It is built without a console window.
  Set `console=True` in `packaging/ofm_webcam_gui.spec`, rebuild, and run it from
  a terminal to see the traceback. (`--help` and argument errors open in a
  dialog instead of the console.)
- **Windows Defender flags a fresh `.exe`** the first time. This is common with
  single-file PyInstaller builds.
- **A language is missing from the built app.** The build packs the compiled
  `.mo` files that are committed. Run `python tools/i18n.py compile` after
  editing a `.po` file (see [TRANSLATING.md](TRANSLATING.md)).
- **The About dialog says the license file was not found.** The spec must bundle
  `LICENSE` (it does: the `datas.append(...)` line for it); if you changed the
  spec, keep that line.
- **Nothing visible when a windowed build crashes.** Uncaught exceptions are
  written to the session log: run with `--save-log` and read the file (or switch
  on **Save log to file** in the window), or use `console=True` as above.

## The Debian package

- `build_deb.sh` builds in a staging folder (`build/deb`), so the repository
  tree stays clean. The package version is read from `core/version.py`.
- It depends on `libgl1` and `libxkbcommon-x11-0`; the rest of Qt's X11
  libraries are bundled in the binary. Not yet verified on a clean machine.
- The license is installed as `/usr/share/doc/ofm-webcam-gui/copyright`, where
  Debian expects it (the binary also carries its own copy for the in-app dialog).
- The menu entry names an icon (`Icon=ofm-webcam-gui`) but no icon file is
  shipped yet, so menus show a generic icon. To add one, put
  `ofm-webcam-gui.png` (or `.svg`) in `packaging/linux/debian/usr/share/pixmaps/`.

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
  `.deb` build installs it as `copyright`, and `core/app_info.py::load_license_text()`
  reads it (from the code folder, or from the package metadata for pip installs).
- **Version:** `core/version.py` only. `pyproject.toml`, the window title, the
  `.deb` build and the translation tool all read it.
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
