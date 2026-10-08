# -*- mode: python ; coding: utf-8 -*-
# Shared PyInstaller spec (Windows + Linux). Run from the repo root:
#   pyinstaller packaging/ofm_webcam_gui.spec
# PyInstaller cannot cross-compile: build on Windows for .exe, on Linux for ELF.
import sys
from pathlib import Path
from PyInstaller.utils.hooks import collect_submodules

REPO_ROOT = Path(SPECPATH).parent
IS_WIN = sys.platform.startswith("win")

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

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="ofm-webcam-gui",   # PyInstaller appends .exe on Windows
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,               # UPX can corrupt Qt DLLs and raises AV false positives
    runtime_tmpdir=None,
    console=False,           # no terminal window; set True to debug a crashing build
)
