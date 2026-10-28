#!/usr/bin/env bash
# Step 1 (Linux): build the PyInstaller folder dist/linux/ofm-webcam-gui/.
# Step 2 is packaging/linux/build_appimage.sh, which wraps it into an AppImage.
# Can be run from any folder.
set -euo pipefail
source "$(dirname "${BASH_SOURCE[0]}")/lib/common.sh"
cd "$REPO_ROOT"

[ -d venv ] || python3 -m venv venv
source venv/bin/activate
pip install -r requirements/linux.txt pyinstaller
pyinstaller --noconfirm --distpath dist/linux --workpath build/linux packaging/ofm_webcam_gui.spec
echo "Built: dist/linux/ofm-webcam-gui/ofm-webcam-gui"
