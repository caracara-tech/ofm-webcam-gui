#!/usr/bin/env bash
# Build dist/linux/ofm-webcam-gui. Run from repo root: ./packaging/build_linux.sh
set -euo pipefail
[ -d venv ] || python3 -m venv venv
source venv/bin/activate
pip install -r requirements/linux.txt pyinstaller
pyinstaller --noconfirm --distpath dist/linux --workpath build/linux packaging/ofm_webcam_gui.spec
echo "Built: dist/linux/ofm-webcam-gui"
