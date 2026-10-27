#!/usr/bin/env bash
# Package the PyInstaller Linux binary (built by build_linux.sh) as a .deb.
# Run from the repository root, AFTER build_linux.sh:
#   ./packaging/linux/build_deb.sh
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
BIN="$REPO_ROOT/dist/linux/ofm-webcam-gui"
TEMPLATE="$REPO_ROOT/packaging/linux/debian"
STAGE="$REPO_ROOT/build/deb"

if [ ! -f "$BIN" ]; then
    echo "error: $BIN not found. Run packaging/build_linux.sh first." >&2
    exit 1
fi

# The version is defined once, in core/version.py.
VERSION="$(sed -n 's/^__version__ = "\(.*\)"$/\1/p' "$REPO_ROOT/core/version.py")"
[ -n "$VERSION" ] || { echo "error: could not read the version from core/version.py" >&2; exit 1; }

# Build in a staging copy so the repository tree stays clean.
rm -rf "$STAGE"
mkdir -p "$STAGE"
cp -r "$TEMPLATE/." "$STAGE/"
mkdir -p "$STAGE/usr/bin"
cp "$BIN" "$STAGE/usr/bin/ofm-webcam-gui"
chmod 755 "$STAGE/usr/bin/ofm-webcam-gui"
sed -i "s/@VERSION@/$VERSION/" "$STAGE/DEBIAN/control"
# Debian expects the license text at /usr/share/doc/<package>/copyright.
install -Dm644 "$REPO_ROOT/LICENSE" "$STAGE/usr/share/doc/ofm-webcam-gui/copyright"

OUT="$REPO_ROOT/dist/linux/ofm-webcam-gui_${VERSION}_amd64.deb"
dpkg-deb --build --root-owner-group "$STAGE" "$OUT"

echo
echo "Built: $OUT"
echo "Install with: sudo apt install $OUT"
