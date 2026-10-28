#!/usr/bin/env bash
# Step 2 (macOS): wrap the .app built by packaging/build_macos.sh into a .dmg
# (drag-to-Applications disk image). Run on a Mac.
set -euo pipefail
source "$(dirname "${BASH_SOURCE[0]}")/../lib/common.sh"

[ "$(uname -s)" = "Darwin" ] || die "this script must run on macOS"

APP="$REPO_ROOT/dist/macos/OFM Webcam Viewer.app"
[ -d "$APP" ] || "$REPO_ROOT/packaging/build_macos.sh"

VERSION="$(app_version)"
STAGE="$REPO_ROOT/build/dmg"
OUT="$REPO_ROOT/dist/macos/ofm-webcam-gui-${VERSION}-$(machine_arch).dmg"

rm -rf "$STAGE" "$OUT"
mkdir -p "$STAGE"
cp -R "$APP" "$STAGE/"
ln -s /Applications "$STAGE/Applications"
hdiutil create -volname "OFM Webcam Viewer $VERSION" -srcfolder "$STAGE" -ov -format UDZO "$OUT"

if [ -n "${CODESIGN_IDENTITY:-}" ]; then
    codesign --force --timestamp --sign "$CODESIGN_IDENTITY" "$OUT"
fi

echo
echo "Built: $OUT"
