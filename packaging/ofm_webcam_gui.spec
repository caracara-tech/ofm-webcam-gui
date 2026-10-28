# -*- mode: python ; coding: utf-8 -*-
# Shared PyInstaller spec (Windows, Linux, macOS). Run from the repo root:
#   pyinstaller packaging/ofm_webcam_gui.spec
# PyInstaller cannot cross-compile: build on each target OS.
#
# Output shape per platform:
#   Windows : one self-contained ofm-webcam-gui.exe          (onefile)
#   Linux   : folder ofm-webcam-gui/ -> wrapped into an AppImage by packaging/linux/build_appimage.sh
#   macOS   : "OFM Webcam Viewer.app" -> wrapped into a .dmg by packaging/macos/build_dmg.sh
# Linux and macOS are onedir on purpose: the AppImage / .dmg is already the
# single distributable file, and a onefile build inside it would unpack itself
# into /tmp on every launch for nothing.
import os
import re
import sys
from pathlib import Path
from PyInstaller.utils.hooks import collect_submodules

REPO_ROOT = Path(SPECPATH).parent
IS_WIN = sys.platform.startswith("win")
IS_MAC = sys.platform == "darwin"
ONEFILE = IS_WIN

APP_NAME = "ofm-webcam-gui"
MAC_APP_NAME = "OFM Webcam Viewer"
MAC_BUNDLE_ID = "tech.caracara.ofm-webcam-gui"
# Read the version from its single definition without importing the package.
VERSION = re.search(r'^__version__ = "(.*)"$', (REPO_ROOT / "core" / "version.py").read_text(), re.M).group(1)

hiddenimports = collect_submodules("hardware") + collect_submodules("core") + collect_submodules("ui")
hiddenimports += ["sangaboard"]
datas, binaries = [], []
if IS_WIN:
    # pygrabber is imported lazily and talks to DirectShow through comtypes
    from PyInstaller.utils.hooks import collect_all
    for pkg in ("pygrabber", "comtypes"):
        d, b, h = collect_all(pkg)
        datas += d; binaries += b; hiddenimports += h

# Compiled translation catalogs (.mo only; the .po sources are not needed at runtime).
for mo in (REPO_ROOT / "core" / "locales").glob("*/LC_MESSAGES/*.mo"):
    datas.append((str(mo), str(mo.parent.relative_to(REPO_ROOT))))

# The license text, shown by the in-app "About / License" dialog (core/app_info.py
# looks for LICENSE at the root of the bundle).
datas.append((str(REPO_ROOT / "LICENSE"), "."))

a = Analysis(
    [str(REPO_ROOT / "app.py")],
    pathex=[str(REPO_ROOT)],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    runtime_hooks=[],
    excludes=["tkinter"],
    noarchive=False,
)
pyz = PYZ(a.pure)

common = dict(
    name=APP_NAME,           # PyInstaller appends .exe on Windows
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,               # UPX can corrupt Qt DLLs and raises AV false positives
    console=False,           # no terminal window; set True to debug a crashing build
)

if ONEFILE:
    exe = EXE(pyz, a.scripts, a.binaries, a.datas, [], runtime_tmpdir=None, **common)
else:
    exe = EXE(pyz, a.scripts, [], exclude_binaries=True, **common)
    coll = COLLECT(exe, a.binaries, a.datas, strip=False, upx=False, name=APP_NAME)
    if IS_MAC:
        # OFM_MACOS_ICON: path to an .icns, set by packaging/build_macos.sh (optional).
        icon = os.environ.get("OFM_MACOS_ICON") or None
        app = BUNDLE(
            coll,
            name=f"{MAC_APP_NAME}.app",
            icon=icon,
            bundle_identifier=MAC_BUNDLE_ID,
            version=VERSION,
            info_plist={
                "CFBundleDisplayName": MAC_APP_NAME,
                "CFBundleShortVersionString": VERSION,
                "LSMinimumSystemVersion": "11.0",
                "NSHighResolutionCapable": True,
                # Without this key macOS kills the app on first camera access.
                "NSCameraUsageDescription": "OFM Webcam Viewer shows the live image of your microscope camera.",
            },
        )
