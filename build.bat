@echo off
setlocal
cd /d "%~dp0"

rem PyInstaller's collect_submodules() imports from sys.path, so make the local
rem humanizer package importable during the build.
set "PYTHONPATH=%CD%;%PYTHONPATH%"

python -m pip install -r requirements.txt
if errorlevel 1 exit /b 1

rem --collect-submodules humanizer is required: streamlit-desktop-app only adds
rem attribute names from "from humanizer.x import y" as hidden imports, so the
rem humanizer package would otherwise be missing from the one-file bundle.
streamlit-desktop-app build app.py --name "AI Text Humanizer" --pyinstaller-options --onefile --collect-submodules humanizer
if errorlevel 1 exit /b 1

echo Built: dist\AI Text Humanizer.exe
