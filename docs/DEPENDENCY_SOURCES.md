# Dependency source and library replacement

This release uses unmodified Python packages resolved by `requirements.lock` and `uv.lock`. The bundled build inventory records exact installed versions, including development tools that are not intentional runtime dependencies. Licence texts are in `third-party-licenses/` and the separate release notices ZIP.

Qt/PySide6/Shiboken6 use the applicable LGPLv3 option; zeroconf uses LGPL-2.1-or-later. No application restriction prevents debugging, reverse engineering for library modification, replacement or rebuilding under these licences. Original B&KG source is MIT licensed and included in Python Portable as well as the repository.

Corresponding library source locations for this build:

- PySide6 and Shiboken6 6.11.2: [official complete source archive](https://download.qt.io/official_releases/QtForPython/pyside6/PySide6-6.11.2-src/pyside-setup-everywhere-src-6.11.2.tar.xz).
- Qt 6.11.2: [official release source directories](https://download.qt.io/official_releases/qt/6.11/6.11.2/) and [qtbase source](https://code.qt.io/cgit/qt/qtbase.git/tag/?h=v6.11.2), [qtsvg source](https://code.qt.io/cgit/qt/qtsvg.git/tag/?h=v6.11.2).
- zeroconf 0.151.3: [release source](https://pypi.org/project/zeroconf/0.151.3/#files).
- Python 3.12.14: [CPython source](https://github.com/python/cpython/tree/v3.12.14).
- Other package source distributions: use the exact versions listed in the inventory and the files on each package's PyPI release page. NumPy's licence includes its bundled numeric-library notices.

To use a modified compatible library, extract Python Portable, create a development environment as in BUILDING.md, install/build your modified library there, and run `BnKG_Run_Python.py`. To rebuild the EXEs, run `python scripts/build_windows.py` in that environment. Build tools do not verify signatures or reject modified libraries. You may update lock files for your modified dependencies; do not represent those packages as the original release.

Executable Portable keeps dynamic libraries under `_internal/`. Replace ABI-compatible library files and their dependencies there after backing up the folder. If module/version/layout changes require recollection, rebuild from the included source. Standalone extracts its embedded dynamic libraries to a temporary folder at runtime; rebuild the single EXE from source to make a persistent modified version. Use the Python/onedir edition for easiest inspection and replacement.

Licensing references: [Qt licensing](https://doc.qt.io/qt-6/licensing.html), [Qt LGPL obligations](https://www.qt.io/development/open-source-lgpl-obligations), [PyInstaller bootloader exception](https://pyinstaller.org/en/stable/license.html). Component licence texts control; this guide is not a blanket legal certification.

Audio update 2026-10-02: websockets 17.0.1, BSD-3-Clause; [exact release/source distribution](https://pypi.org/project/websockets/17.0.1/#files), [licence](licenses/websockets-LICENSE.txt). Included in runtime locks and normal build dependency/licence collection; the refreshed packages include its notices.


## Qt Multimedia playback — 2026-10-10

Runtime now also pins **PySide6-Addons 6.11.2**. Qt Multimedia and its widgets use the applicable LGPLv3 route. Sources: [PySide 6.11.2](https://download.qt.io/official_releases/QtForPython/pyside6/PySide6-6.11.2-src/pyside-setup-everywhere-src-6.11.2.tar.xz), [Qt Multimedia v6.11.2](https://code.qt.io/cgit/qt/qtmultimedia.git/tag/?h=v6.11.2), and the Qt source directory above. Review collected modules when packaging; installing Addons does not mean every Addons module should be bundled.

The installed Windows playback libraries report **FFmpeg 7.1.5**, **LGPL version 2.1 or later**. [Exact upstream source tag](https://github.com/FFmpeg/FFmpeg/tree/n7.1.5), [licence text](https://github.com/FFmpeg/FFmpeg/blob/n7.1.5/COPYING.LGPLv2.1), [FFmpeg redistribution guidance](https://ffmpeg.org/legal.html). The observed configuration enables shared libraries, disables static libraries/programs/docs/avdevice/avfilter, uses MSVC, and enables zlib with a zlib-1.3.1 build path. No GPL/nonfree flag is present. Preserve full configuration/inventory when building; the public build record is in `packaging/source-provenance/windows-ffmpeg-build.json`. `avcodec-61.dll` SHA-256: `3823070d38dc7dce277ccec165f99bbc02ad96bacc9afde1a00818e9d8350eb6`.

The release source ZIP supplies Qt/PySide and FFmpeg corresponding source archives, Qt 6.11.2 provisioning/build scripts and zlib 1.3.1. Its manifest records original URLs and SHA-256 hashes. The exact FFmpeg n7.1.5 archive also matches the SHA-1 in Qt's release provisioning script. Unmodified build-script excerpts and the observed Windows FFmpeg configuration are in packaging/source-provenance/. No local library patches were applied. Use the Python/onedir edition and the replacement instructions above to run modified libraries. The source ZIP is hosted alongside binaries on GitHub Releases; external encoder executables remain excluded.


2026-10-10: Pillow 12.3.0 is pinned in runtime locks for local display resampling. [Exact release/source distribution](https://pypi.org/project/pillow/12.3.0/#files), [upstream tag](https://github.com/python-pillow/Pillow/tree/12.3.0), [complete installed notices](licenses/Pillow-LICENSE.txt). Existing build licence collection includes the wheel licence directory. Optional EXE packaging must inventory collected Pillow codec libraries; the refreshed packages collect the installed notices.
