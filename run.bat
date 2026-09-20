@echo off
REM VaniGuard launcher — always runs with the venv's Python (3.12)
REM which has all required packages: miniaudio, librosa, onnxruntime, etc.
REM Usage: double-click this file, or run it from any terminal.

cd /d "%~dp0"
echo Starting VaniGuard with venv Python...
"%~dp0venv\Scripts\streamlit.exe" run app.py %*
