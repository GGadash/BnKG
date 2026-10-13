import sys
from pathlib import Path

from PySide6.QtCore import QSettings

from bnkg.core.media_tools import media_tools
from bnkg.ui.recording import RecordingPanel


def pair(folder):
    folder.mkdir(parents=True, exist_ok=True)
    suffix = ".exe" if sys.platform == "win32" else ""
    paths = [folder / (name + suffix) for name in ("ffmpeg", "ffprobe")]
    for path in paths:
        path.touch()
    return tuple(str(p) for p in paths)


def test_media_discovery_precedence_and_moved_settings(tmp_path, monkeypatch):
    monkeypatch.setattr("bnkg.core.media_tools.shutil.which", lambda _: None)
    assert media_tools("missing-encoder", "missing-probe", app_root=tmp_path) == (
        "missing-encoder",
        "missing-probe",
    )
    local = pair(tmp_path / "external-tools/ffmpeg/bin")
    assert media_tools("missing", "missing", app_root=tmp_path) == local
    saved = pair(tmp_path / "chosen build")
    assert media_tools(*saved, app_root=tmp_path) == saved
    assert media_tools(saved[0], "missing", app_root=tmp_path) == saved
    Path(local[1]).unlink()
    assert media_tools(app_root=tmp_path) == ("", "")
    monkeypatch.setattr("bnkg.core.media_tools.shutil.which", lambda _: saved[0])
    assert media_tools(app_root=tmp_path) == saved


def test_missing_tools_guidance_and_browse_same_build(qtbot, tmp_path, monkeypatch):
    monkeypatch.setattr("bnkg.ui.recording.media_tools", lambda *a: ("", ""))
    settings = QSettings(str(tmp_path / "settings.ini"), QSettings.Format.IniFormat)
    panel = RecordingPanel(settings, tmp_path)
    qtbot.addWidget(panel)
    panel.mp4.setChecked(True)
    panel.set_connected(True)
    panel.start_recording()
    assert panel.job is None and "Browse" in panel.status.text()
    assert "missing" in panel.tool_status.text()
    tools = pair(tmp_path / "chosen build")
    monkeypatch.setattr("bnkg.ui.recording.QFileDialog.getOpenFileName", lambda *a: (tools[0], ""))
    panel.choose_tool(panel.ffmpeg)
    assert (panel.ffmpeg.text(), panel.ffprobe.text()) == tools
    assert settings.value("ffprobe_path") == tools[1]
    assert "Tool files found" in panel.tool_status.text()
