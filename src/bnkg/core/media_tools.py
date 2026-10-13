"""Locate optional external media tools without running or downloading them."""

import shutil
import sys
from pathlib import Path

DOWNLOAD_URL = "https://www.gyan.dev/ffmpeg/builds/"
OFFICIAL_URL = "https://ffmpeg.org/download.html"


def media_tools(ffmpeg="", ffprobe="", *, app_root=None):
    """Prefer saved choices, then the adjacent local installation, then PATH."""
    if ffmpeg and ffprobe and Path(ffmpeg).is_file() and Path(ffprobe).is_file():
        return str(ffmpeg), str(ffprobe)
    suffix = ".exe" if sys.platform == "win32" else ""
    if ffmpeg and Path(ffmpeg).is_file():
        sibling = Path(ffmpeg).with_name("ffprobe" + Path(ffmpeg).suffix)
        if sibling.is_file():
            return str(ffmpeg), str(sibling)
    root = (
        Path(app_root)
        if app_root is not None
        else (
            Path(sys.executable).resolve().parent
            if getattr(sys, "frozen", False)
            else Path(__file__).resolve().parents[3]
        )
    )
    folder = root / "external-tools" / "ffmpeg" / "bin"
    pair = tuple(folder / (name + suffix) for name in ("ffmpeg", "ffprobe"))
    if all(path.is_file() for path in pair):
        return tuple(str(path) for path in pair)
    found = shutil.which("ffmpeg")
    if found:
        probe = Path(found).with_name("ffprobe" + Path(found).suffix)
        if probe.is_file():
            return found, str(probe)
    # Preserve missing explicit paths for recovery after moving machines.
    return str(ffmpeg), str(ffprobe)
