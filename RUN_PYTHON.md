# B&KG — Run the Python app

**Automated option:** copy `Rename-And-Setup-BnKG.cmd` and `Rename-And-Setup-BnKG.ps1` to the parent folder, close the app/Codex, then run the CMD there. It verifies and renames HBKG → BnKG, preserves/recreates .venv, installs dependencies and checks startup. Already renamed? Run `Setup-BnKG-After-Move.cmd` inside the project. Read `SETUP_AND_RENAME_INSTRUCTIONS.txt` for step-by-step instructions and recovery. Reopen the new Codex project manually afterward.

**B&KG = BnKG.** Recommended project folder: **`BnKG`**; rename the existing folder using the numbered steps in [Moving the project](BUILDING.md). Display name: **B&KG - SLM Remote Desktop Studio for Open API of HBK 2255 & B&K 2245, by Gadash**. Python package: `bnkg`; source launcher: `BnKG_Run_Python.py`. Graphic wordmarks intentionally retain their existing design. See `BUILDING.md` for moving or renaming the project folder.

This app is under construction. Information may be incomplete, delayed or displayed incorrectly; double-check it on the instrument. Updates and related releases: [https://github.com/GGadash](https://github.com/GGadash). Optional support: [Ko-fi](https://ko-fi.com/gadash).

Current source: 0.4.0a1. Installer EXE and portable application builds are deferred during development. Old dist/ binaries are previous snapshots; Launch-BnKG.cmd now always starts source.

## Requirements

- Minimum Python: **3.12**. Declared range: Python **3.12–3.14**; tested here with **64-bit Python 3.12.14 on Windows**. Use 3.12 for the closest match to validation.
- Install dependencies from requirements.lock: PySide6-Essentials, Requests, pyqtgraph/NumPy, openpyxl and zeroconf, with their pinned transitive dependencies.
- Internet access is needed for the first dependency installation unless you have a matching offline wheel cache.
- Keep BnKG_Run_Python.py, src/, requirements.lock and the rest of this project together. The .py file is an entry point, not a self-contained bundle.

## First setup on a new Windows PC

Install Python 3.12 (64-bit) from python.org with the Python launcher. Open cmd or PowerShell in this project directory:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --require-hashes -r requirements.lock
.\.venv\Scripts\python.exe BnKG_Run_Python.py
```

No virtual-environment activation or PowerShell execution-policy change is needed. If the Python launcher is unavailable, use the full path to your installed Python 3.12 executable for the first command.

## Everyday launch

- Double-click Launch-BnKG.cmd, or run it from cmd/PowerShell.
- From cmd or PowerShell: `.\.venv\Scripts\python.exe BnKG_Run_Python.py`.
- Directly double-click BnKG_Run_Python.py if Windows associates .py files with Python. It reuses the project .venv when available. With no .venv, the associated Python must be 3.12–3.14 and have the dependencies installed.
- Optional synthetic demo: append `--demo` to open the isolated Demo Lab.
- To put sessions/preferences in a folder you will move between PCs: append `--data-dir local-data`. This is optional; otherwise the app uses the Windows per-user local application-data folder.

Do not copy .venv to another PC. Copy the source/project and your measurement data, then recreate the environment. Read BUILDING.md and CONTRIBUTING.md before continuing development.

## First use

Connection accepts an editable address or discovered SLM. Dashboard, Frequency Analysis and Metadata read actual instrument outputs; stopped/disabled cumulative results can be unavailable. Select metadata fields to show on Dashboard. Read CONNECTION_GUIDE.md and docs/METADATA_CAPABILITIES.md.

Local capture/logging controls are under **Data table**. Monitoring updates current readings without adding table history or opening a file. Start local capture for table/trend history; Start file logging for a complete timestamped SQLite session. Stop logging leaves capture running; Stop capture or Disconnect closes logging. Default table limit 100, adjustable 1–999, does not truncate the logged file.

**Demo Lab** is independent: three scenarios, synthetic frequency preview and a simple main-values CSV. Pause/stop creates no repeated rows. It can run while the main instrument remains connected, without mixing either data source.

SLM Screen keeps the last image when stale/disconnected and offers native-resolution PNG save. Identify is a deliberate guarded device action, not automatic power wake. Original-frame recording, FLAC capture, playback and optional external FFmpeg media export are available; see docs/RECORDING_PLAN.md and docs/AUDIO_CAPTURE.md. About includes developer and Ko-fi links with copy buttons and feedback.

Location: Metadata now includes manual coordinates (initially empty; not an acquired fix), copying valid SLM coordinates and a guarded transfer to one enabled Text slot. This does not change native GPS. Two confirmations, arming, idle-state/access checks, read-back and a local audit apply. Automatic PC/phone location is pending. See [location transfer instructions](docs/LOCATION_TRANSFER.md). Live writes were not tested.
