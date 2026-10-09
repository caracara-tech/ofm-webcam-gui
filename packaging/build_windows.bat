@echo off
REM Build dist\windows\ofm-webcam-gui.exe. Can be run from any folder.
setlocal

REM Work from the repository root (this file lives in <root>\packaging), so the
REM relative paths below are right no matter where the script is started from.
cd /d "%~dp0.."

if not exist venv (
    python -m venv venv || exit /b 1
)
call venv\Scripts\activate.bat || exit /b 1
pip install -r requirements\windows.txt pyinstaller || exit /b 1
pyinstaller --noconfirm --distpath dist\windows --workpath build\windows packaging\ofm_webcam_gui.spec || exit /b 1
echo Built: dist\windows\ofm-webcam-gui.exe
endlocal
