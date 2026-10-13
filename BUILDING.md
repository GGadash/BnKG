# Build and verify B&KG

Packaging and publication were authorized on 2026-09-20. Windows x64 Python 3.12.14 is the tested build runtime; the source declares Python 3.12–3.14.

Create `.venv` with Python 3.12, then install pinned tools:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install --require-hashes -r requirements-dev.lock
.\.venv\Scripts\python.exe -m pip check
.\.venv\Scripts\python.exe -m ruff check src tests scripts BnKG_Run_Python.py
$env:QT_QPA_PLATFORM = 'windows'
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe scripts/build_windows.py
```

The source launcher supplies `src/` automatically; an editable install is optional. Hardware writes are excluded from default tests. Build tooling never contacts the SLM, creates a tag or publishes anything. It produces the Standalone EXE, executable Portable ZIP, Python Portable ZIP, notices and SHA-256 files in `release-assets/`. Staging files go to ignored `dist/` and `build/`.

PyInstaller builds use a restricted PATH to avoid unrelated Qt/ICU DLLs. Both modes use clean dependency analysis. The Python package is curated from source, tests, build/setup tools and public guides; no `.venv`, Git history, private archive, credentials or measurement logs are included. `--package-only` refreshes documentation/ZIPs around existing binaries; use it only when application code has not changed since freezing.

Verify the executable Portable from a newly extracted path containing spaces:

```powershell
.\.venv\Scripts\python.exe scripts/verify_portable.py release-assets/BnKG-0.4.0a1-win64-Executable-Portable.zip
```

Also run the Standalone EXE with `--smoke-test --data-dir <isolated-folder>` using Windows-only PATH, and verify the Python Portable in a newly created environment with pinned runtime dependencies. Smoke results must report version 0.4.0a1, source disconnected, logging false and no active session. Use actual display scaling/clean-Windows acceptance separately; a same-PC check cannot prove it.

Binaries are unsigned. See [dependency source/replacement directions](docs/DEPENDENCY_SOURCES.md). Only after all package checks pass should the maintainer commit, create an annotated pre-release tag, push and upload explicit release assets. Private project migration ZIPs must never be release assets.

For this home checkout's Git ownership mismatch, use `git -c safe.directory=E:/AI/OpenAI/Codex/BnKG <command>`; do not trust every directory globally.

## Linux and public-source preparation

See [Ubuntu setup](docs/LINUX.md). Build on Ubuntu 22.04 x86-64 using `python scripts/build_linux.py`; validate the extracted bundle on both target Ubuntu releases with `xvfb-run -a python scripts/verify_linux.py <archive>`. GitHub Actions performs these tasks on explicit workflow dispatch, without device access.

`python scripts/prepare_public_source.py <separate-directory>` stages the explicit public allowlist. It excludes local progress/handoffs, private exports/artifacts, supplied reference materials, installed tools and old releases. The local development history is retained separately; never push that private history as the public branch.

Fetch corresponding source archives using `python scripts/fetch_library_sources.py`; retain the source manifest and package the verified sources beside binaries. The Qt provisioning archive supplies exact upstream FFmpeg build instructions. Final public-source and package checks must match the tagged source.
