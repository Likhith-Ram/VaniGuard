@echo off
REM VaniGuard launcher — runs with the venv's Python (3.10+)
REM Required packages: miniaudio, librosa, onnxruntime, streamlit, etc.
REM Usage: double-click this file, or run it from any terminal in the repo root.

cd /d "%~dp0"
echo Starting VaniGuard with venv Python...
"%~dp0venv\Scripts\streamlit.exe" run ui/app.py %*
