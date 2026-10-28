#!/usr/bin/env bash
# Step 2 (Linux): wrap dist/linux/ofm-webcam-gui/ into a single-file AppImage.
#   ./packaging/linux/build_appimage.sh        (runs build_linux.sh itself if needed)
#
# Compatibility: an AppImage runs on any distribution whose glibc is at least
# as new as the one of the machine that built it. Build on the OLDEST
# distribution you want to support (the CI job uses Ubuntu 22.04), never on a
# rolling release.
#
# Environment overrides:
#   APPIMAGETOOL   path of an appimagetool to use instead of downloading one
set -euo pipefail
source "$(dirname "${BASH_SOURCE[0]}")/../lib/common.sh"

ARCH="$(machine_arch)"
case "$ARCH" in
    x86_64|aarch64) ;;
    *) die "unsupported architecture '$ARCH' (AppImage builds: x86_64, aarch64)" ;;
esac

# Pinned download of the packaging tool, verified against a known checksum.
APPIMAGETOOL_VERSION="1.9.0"
declare -A APPIMAGETOOL_SHA256=(
    [x86_64]="46fdd785094c7f6e545b61afcfb0f3d98d8eab243f644b4b17698c01d06083d1"
    [aarch64]="04f45ea45b5aa07bb2b071aed9dbf7a5185d3953b11b47358c1311f11ea94a96"
)

SRC="$REPO_ROOT/dist/linux/ofm-webcam-gui"
TEMPLATE="$REPO_ROOT/packaging/linux/appimage"
ICON="$REPO_ROOT/packaging/assets/ofm-webcam-gui.png"
BUILD="$REPO_ROOT/build/appimage"
APPDIR="$BUILD/AppDir"
VERSION="$(app_version)"
OUT="$REPO_ROOT/dist/linux/ofm-webcam-gui-${VERSION}-${ARCH}.AppImage"

[ -x "$SRC/ofm-webcam-gui" ] || "$REPO_ROOT/packaging/build_linux.sh"
[ -f "$ICON" ] || die "missing icon: $ICON"
# appimagetool validates the .desktop file with this (Debian/Ubuntu: apt install desktop-file-utils).
command -v desktop-file-validate >/dev/null || die "desktop-file-validate not found (apt install desktop-file-utils)"

fetch_appimagetool() {
    local tool="$BUILD/appimagetool-$APPIMAGETOOL_VERSION-$ARCH.AppImage"
    if [ ! -x "$tool" ]; then
        mkdir -p "$BUILD"
        curl -fsSL -o "$tool" \
            "https://github.com/AppImage/appimagetool/releases/download/$APPIMAGETOOL_VERSION/appimagetool-$ARCH.AppImage"
        echo "${APPIMAGETOOL_SHA256[$ARCH]}  $tool" | sha256sum -c - >&2 \
            || { rm -f "$tool"; die "appimagetool checksum mismatch"; }
        chmod +x "$tool"
    fi
    printf '%s\n' "$tool"
}
TOOL="${APPIMAGETOOL:-$(fetch_appimagetool)}"

# Assemble the AppDir in a staging folder so the repository tree stays clean.
rm -rf "$APPDIR"
mkdir -p "$APPDIR/usr/lib" "$APPDIR/usr/share/applications" \
         "$APPDIR/usr/share/icons/hicolor/256x256/apps" "$APPDIR/usr/share/doc/ofm-webcam-gui"
cp -r "$SRC" "$APPDIR/usr/lib/ofm-webcam-gui"
install -m755 "$TEMPLATE/AppRun" "$APPDIR/AppRun"
install -m644 "$TEMPLATE/ofm-webcam-gui.desktop" "$APPDIR/ofm-webcam-gui.desktop"
install -m644 "$TEMPLATE/ofm-webcam-gui.desktop" "$APPDIR/usr/share/applications/"
install -m644 "$ICON" "$APPDIR/ofm-webcam-gui.png"
install -m644 "$ICON" "$APPDIR/usr/share/icons/hicolor/256x256/apps/ofm-webcam-gui.png"
ln -sf ofm-webcam-gui.png "$APPDIR/.DirIcon"
install -m644 "$REPO_ROOT/LICENSE" "$APPDIR/usr/share/doc/ofm-webcam-gui/copyright"

# --appimage-extract-and-run: works on build machines without FUSE (containers, CI).
rm -f "$OUT"
ARCH="$ARCH" "$TOOL" --appimage-extract-and-run --no-appstream "$APPDIR" "$OUT"

# Smoke test: the packaged program must start and answer --help without a display.
QT_QPA_PLATFORM=offscreen APPIMAGE_EXTRACT_AND_RUN=1 "$OUT" --help >/dev/null \
    || die "smoke test failed: $OUT --help"

echo
echo "Built: $OUT"
echo "Run with: chmod +x '$OUT' && '$OUT'"
