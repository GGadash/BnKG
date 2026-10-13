@echo off
cd /d "%~dp0"
if exist ".venv\Scripts\python.exe" (
    ".venv\Scripts\python.exe" "BnKG_Run_Python.py" %*
) else (
    py -3 "BnKG_Run_Python.py" %*
)
if errorlevel 1 (
    echo Read RUN_PYTHON.md. BnKG requires Python 3.12-3.14 and its dependencies.
    pause
)
