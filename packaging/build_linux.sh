#!/usr/bin/env bash
# Build dist/linux/ofm-webcam-gui. Can be run from any folder.
set -euo pipefail

# Work from the repository root (this file lives in <root>/packaging), so the
# relative paths below are right no matter where the script is started from.
cd "$(dirname "${BASH_SOURCE[0]}")/.."

[ -d venv ] || python3 -m venv venv
source venv/bin/activate
pip install -r requirements/linux.txt pyinstaller
pyinstaller --noconfirm --distpath dist/linux --workpath build/linux packaging/ofm_webcam_gui.spec
echo "Built: dist/linux/ofm-webcam-gui"
