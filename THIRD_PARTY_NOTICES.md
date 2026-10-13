# B&KG — Third-Party Notices

Original code: MIT, Copyright (c) 2026 Gadash (Akila DJ).

The resolved set is in uv.lock. Local packages include available installed licence texts under third-party-licenses and a build-environment inventory. The inventory includes development tools and is not a minimal runtime bill of materials. See docs/DEPENDENCY_SOURCES.md for exact-version source locations and library replacement/rebuild instructions.

| Component | Role | Reference |
| --- | --- | --- |
| Python 3.12 | Runtime | PSF terms: https://docs.python.org/3/license.html |
| PySide6-Essentials / PySide6-Addons / Shiboken6 / Qt | UI | Applicable Qt LGPL/GPL/commercial terms: https://doc.qt.io/qtforpython-6/licenses.html ; individual module and third-party notices control |
| Requests | HTTP | Apache-2.0; installed notices |
| urllib3, certifi, charset-normalizer, idna | HTTP dependencies | Individual installed licence texts |
| pyqtgraph | Charts | MIT; installed text |
| NumPy | Numeric/chart dependency | BSD and bundled third-party terms; installed texts |
| openpyxl / et-xmlfile | XLSX | Individual installed texts |
| zeroconf / ifaddr | Local mDNS discovery / interface enumeration | zeroconf LGPL-2.1-or-later; ifaddr MIT; installed distribution notices |
| SQLite | Local data | Public domain core: https://www.sqlite.org/copyright.html |
| PyInstaller and hooks | Build | GPL with bootloader exception: https://pyinstaller.org/en/stable/license.html |
| pytest, pytest-qt, Ruff and build tooling | Development | Installed metadata/texts; not intentional runtime dependencies |

Qt remains in separate dynamic libraries. B&KG introduces no restriction on debugging/replacement for applicable LGPL purposes. The Python Portable includes application source, locks and build scripts for rebuilding with modified libraries. The standalone EXE embeds notices, available with --extract-notices; release notices are also provided separately. See docs/DEPENDENCY_SOURCES.md. No claim of independent legal certification is made.

No optional FFmpeg command-line executable, HBK manuals, proprietary logos or example source modules are redistributed. Qt playback library dependencies are described below. OpenAI tools assisted development and are not runtime dependencies.

0.3.0a1 adds original inline SVG wordmarks rendered using QtSvgWidgets, already in PySide6-Essentials. No new Python dependency or external binary was added. The official SLM API package was consulted as a reference only and is not imported or redistributed. This historical milestone deferred FFmpeg/video/audio; see the stage 5 update below.


Stage 5 (2026-09-28) adds optional invocation of user-selected external FFmpeg/libx264 and ffprobe. No encoder binary, source module or new Python dependency is bundled. PNG sequence recording works without FFmpeg. Licence obligations depend on the external build configuration; any future bundling requires an exact-build licence/source review. References: [FFmpeg legal information](https://ffmpeg.org/legal.html), [codec documentation](https://ffmpeg.org/ffmpeg-codecs.html#libx264_002c-libx264rgb). Audio was unavailable at this historical milestone; current capture/playback is described below. See the 2026-10-01 update below for local installation/acceptance.

Stage 6 (2026-09-29) uses existing Qt/Python/SQLite/Requests components only. Coordinate links open the external OpenStreetMap website on explicit user action; no map tiles, map SDK or service credentials are bundled.

Stage 7 (2026-09-30) uses existing Python standard-library JSON/hash/SQLite/file handling and Qt/pyqtgraph components. No new library, external binary or network integration was added.

Stage 8 (2026-10-01) uses existing Qt settings/widgets and Python JSON only. No new dependencies, external services or bundled assets.

Stage 9 (2026-10-01) uses existing Python JSON/dataclasses and Qt settings/widgets. The existing exporter dependencies are unchanged; no new external service or binary.


2026-10-01: optional **Gyan FFmpeg 9.0.2 Essentials (GPLv3)** installed locally under ignored `external-tools/ffmpeg/`, with original LICENSE/README/docs and checksum/provenance retained. It is not included in Git, generated packages or transfer exports. x264, native FLAC/AAC and libopus are available; FDK-AAC is absent. x264 plus FDK-AAC would require a non-redistributable nonfree build under the documented FFmpeg configuration. See [setup, exact archive hash and licence/source references](docs/FFMPEG_SETUP.md) and [FFmpeg licensing](https://ffmpeg.org/doxygen/trunk/md_LICENSE.html). No Python dependency or application audio feature was added. Future encoder bundling requires a separate exact-build redistribution review.

2026-10-02: `websockets` 17.0.1 (BSD-3-Clause) provides bounded instrument audio transport. Copyright Aymeric Augustin and contributors; complete [licence](docs/licenses/websockets-LICENSE.txt), [upstream source](https://github.com/python-websockets/websockets/tree/17.0.1). Native app FLAC capture now exists; earlier audio-unavailable statements above are historical. Optional FFmpeg remains external.


2026-10-10: playback adds **PySide6-Addons 6.11.2 / Qt Multimedia**, using the applicable LGPLv3 option and original Qt notices. The installed Windows wheel supplies **FFmpeg 7.1.5 shared libraries** (`avcodec-61`, `avformat-61`, `avutil-59`, `swresample-5`); their runtime licence reports **LGPL version 2.1 or later**, with shared-library build configuration and no enable-gpl/nonfree flag. FFmpeg is copyright its respective developers/contributors; no local modifications were made. The exact LGPL-2.1 text is included under `packaging/licenses/`. This playback dependency is distinct from the optional local Gyan FFmpeg 9.0.2 GPLv3 encoder executables. Source/build references and source/build provenance are in [DEPENDENCY_SOURCES.md](docs/DEPENDENCY_SOURCES.md). The refreshed release packages include these libraries and notices.


2026-10-10: Pillow 12.3.0 adds local nearest-neighbor/Lanczos/bicubic display resampling. Complete installed wheel notice (including bundled-library notices) is retained in [docs/licenses/Pillow-LICENSE.txt](docs/licenses/Pillow-LICENSE.txt); HPND/Pillow and individual third-party terms apply. No original manufacturer image is changed. See the exact source references in docs/DEPENDENCY_SOURCES.md.

## Release source archives

This software uses FFmpeg playback libraries under LGPL-2.1-or-later. Corresponding sources for FFmpeg, Qt/PySide and zeroconf are supplied alongside the [binary release](https://github.com/GGadash/BnKG/releases), with build scripts, source URLs and hashes. See [source and replacement instructions](docs/DEPENDENCY_SOURCES.md). Python Portable contains the MIT application source and build scripts. Optional Gyan encoder executables are not redistributed.
