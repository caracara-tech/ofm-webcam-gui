@echo off
REM Build dist\windows\ofm-webcam-gui.exe. Run from repo root: packaging\build_windows.bat
setlocal
if not exist venv python -m venv venv
call venv\Scripts\activate.bat
pip install -r requirements\windows.txt pyinstaller || exit /b 1
pyinstaller --noconfirm --distpath dist\windows --workpath build\windows packaging\ofm_webcam_gui.spec || exit /b 1
echo Built: dist\windows\ofm-webcam-gui.exe
endlocal
