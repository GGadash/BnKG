# Project and package contents

Start with [README-INFO.md](README-INFO.md), [README.md](README.md) and [the documentation index](docs/README.md).

| Location | Purpose | Distribution |
| --- | --- | --- |
| Root README/info, quick start, credits, licence and notices | Essential end-user information | GitHub and end-user packages |
| `src/bnkg/` | Shared device/safety layer, processing and Qt UI | Repository and Python Portable |
| `tests/` | Offline tests and synthetic fixtures | Repository and Python Portable |
| `scripts/` | Setup, build, source inventory and package checks | Curated public scripts |
| `docs/` | User guides and advanced technical references | Curated public documents |
| `docs/screenshots/` | Ten historical, labelled application PNG previews | Public; interface may have changed |
| `docs/wiki/` | Editable Wiki page sources | GitHub; Wiki also published separately |
| `packaging/licenses/` | Component licence texts | Public packages |
| `.github/workflows/` | Linux build and smoke-check workflow | GitHub |
| `release-assets/` | Current packages, sources, notices and hashes | Git ignored; uploaded to Releases |
| `_LOCAL_ARCHIVE/` | Recoverable historical builds and edited-original backups | Local only |
| `_TRANSFER_EXPORTS/` | Private account/machine-transfer snapshots | Local only; never release assets |
| `exports/`, `artifacts/`, `docs/vibe_transfer/` | Private samples, hardware evidence and reference material | Excluded from public source/packages |
| `.venv/`, `.cache/`, `build/`, `dist/` | Local environment and reproducible generated files | Excluded from public source/packages |
| Root numbered progress/requirements, handoffs and `docs/progress/` | Maintainer continuity and historical notes | Preserved locally; not public release content |

Cleanup on 2026-10-14 archived old release assets under `_LOCAL_ARCHIVE/2026-10-14-release-preparation/historical-release-assets/`; only reproducible build and test caches were removed. Private measurements and original development history are retained locally. The user authorized a fresh curated public history. Public packages are assembled from explicit file lists, not whole-folder copies.

The advanced references remain separate from everyday help. [Contributions](CONTRIBUTING.md), [build instructions](BUILDING.md) and [roadmap](ROADMAP.md) describe further development. Private transfer ZIPs are immutable historical snapshots and are not suitable GitHub release assets.
