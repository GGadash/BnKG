"""Collect Qt GUI without unused PDF, virtual-keyboard or Mesa fallback plugins."""

from pathlib import Path

from PyInstaller.utils.hooks.qt import add_qt6_dependencies

hiddenimports, binaries, datas = add_qt6_dependencies(__file__)
hiddenimports = [
    name for name in hiddenimports if name not in {"PySide6.QtPdf", "PySide6.QtVirtualKeyboard"}
]
unused = ("qpdf", "qt6pdf", "qtvirtualkeyboard", "qt6virtualkeyboard", "opengl32sw")
binaries = [
    (source, destination)
    for source, destination in binaries
    if not any(word in Path(source).name.lower() for word in unused)
]
