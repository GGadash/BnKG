"""Collect supported Qt binding helpers without the optional Mesa fallback."""

from pathlib import Path

from PyInstaller.utils.hooks.qt import ensure_single_qt_bindings_package, pyside6_library_info

ensure_single_qt_bindings_package("PySide6")
hiddenimports = ["shiboken6", "inspect", "PySide6.support.deprecated"]
binaries = [
    (source, destination)
    for source, destination in pyside6_library_info.collect_extra_binaries()
    if Path(source).name.lower() != "opengl32sw.dll"
]
