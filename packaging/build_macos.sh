#!/usr/bin/env bash
# Step 1 (macOS): build dist/macos/"OFM Webcam Viewer.app". Must run on a Mac.
# Step 2 is packaging/macos/build_dmg.sh. Can be run from any folder.
#
# The app is built for the architecture of the Mac running this script (Apple
# Silicon -> arm64, Intel -> x86_64): OpenCV ships separate wheels per
# architecture, so build once on each kind of Mac for a universal release.
#
# Environment:
#   CODESIGN_IDENTITY   optional, e.g. "Developer ID Application: Name (TEAMID)".
#                       Without it the app is not signed for distribution and
#                       Gatekeeper asks users to approve it on first launch.
set -euo pipefail
source "$(dirname "${BASH_SOURCE[0]}")/lib/common.sh"
cd "$REPO_ROOT"

[ "$(uname -s)" = "Darwin" ] || die "this script must run on macOS (PyInstaller cannot cross-compile)"

APP="dist/macos/OFM Webcam Viewer.app"
ICON_PNG="packaging/assets/ofm-webcam-gui.png"

[ -d venv ] || python3 -m venv venv
source venv/bin/activate
pip install -r requirements/macos.txt pyinstaller

# .icns from the PNG (sips + iconutil ship with macOS).
ICONSET="build/macos/icon.iconset"
rm -rf "$ICONSET"; mkdir -p "$ICONSET"
for size in 16 32 128 256; do
    sips -z $size $size "$ICON_PNG" --out "$ICONSET/icon_${size}x${size}.png" >/dev/null
    sips -z $((size*2)) $((size*2)) "$ICON_PNG" --out "$ICONSET/icon_${size}x${size}@2x.png" >/dev/null
done
iconutil -c icns "$ICONSET" -o build/macos/icon.icns
export OFM_MACOS_ICON="$REPO_ROOT/build/macos/icon.icns"

pyinstaller --noconfirm --distpath dist/macos --workpath build/macos packaging/ofm_webcam_gui.spec

if [ -n "${CODESIGN_IDENTITY:-}" ]; then
    codesign --force --deep --options runtime --timestamp --sign "$CODESIGN_IDENTITY" "$APP"
    codesign --verify --deep --strict "$APP"
fi

# Smoke test: the bundle must start and answer --help without a display.
QT_QPA_PLATFORM=offscreen "$APP/Contents/MacOS/ofm-webcam-gui" --help >/dev/null \
    || die "smoke test failed: $APP --help"

echo "Built: $APP"
