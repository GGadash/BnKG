import json
import time
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from PySide6.QtCore import QBuffer, QIODevice
from PySide6.QtGui import QImage
from PySide6.QtWidgets import QWidget

from bnkg.core.recording import FrameArchive, RecordingCancelled, run_tool
from bnkg.core.webxi import WebXiClient
from bnkg.ui.components import ScreenPane
from bnkg.ui.recording import RecordingJob
from bnkg.ui.window import MainWindow
from bnkg.ui.worker import AcquisitionWorker


def png(width=241, height=321, color="green"):
    image = QImage(width, height, QImage.Format.Format_RGB32)
    image.fill(color)
    buffer = QBuffer()
    buffer.open(QIODevice.OpenModeFlag.WriteOnly)
    assert image.save(buffer, "PNG")
    return bytes(buffer.data())


def stamp(value):
    return {"monotonic": value, "pc_utc": "2026-09-28T12:00:00+00:00"}


def test_display_modes_original_processed_fullscreen(qtbot, tmp_path):
    view = ScreenPane(QWidget())
    qtbot.addWidget(view)
    view.resize(800, 600)
    view.show()
    data = png()
    view.set_image(data)
    view.zoom.setCurrentIndex(view.zoom.findData(2))
    view.rendering.setCurrentIndex(view.rendering.findData("pixel"))
    assert view.image.pixmap().size().width() == 482
    view.save_png(tmp_path / "original.png")
    view.save_processed_png(tmp_path / "processed.png")
    assert (tmp_path / "original.png").read_bytes() == data
    assert QImage(str(tmp_path / "processed.png")).width() == 482
    with pytest.raises(FileExistsError):
        view.save_processed_png(tmp_path / "processed.png")
    view.hide_controls.setChecked(True)
    assert view.controls.isHidden()
    view.set_status("Disconnected — retained screen")
    received = view.received_at
    view.open_fullscreen()
    other = view.fullscreen_dialog.findChild(ScreenPane)
    assert other.png == data and other.received_at == received and not other.live
    view.fullscreen_dialog.reject()
    qtbot.waitUntil(lambda: view.fullscreen_dialog is None)


def test_archive_bounds_timing_gaps_and_original_bytes(tmp_path, monkeypatch):
    archive = FrameArchive(tmp_path)
    data = png()
    archive.append(data, stamp(1))
    archive.append(data, stamp(6))
    assert archive.rows[1]["gap_before_s"] == 5
    assert archive.rows[1]["unchanged_for_s"] == 5
    assert (archive.folder / archive.rows[0]["file"]).read_bytes() == data
    with pytest.raises(ValueError, match="resolution"):
        archive.append(png(240), stamp(7))
    with pytest.raises(ValueError, match="Non-increasing"):
        archive.append(data, stamp(6))
    monkeypatch.setattr("bnkg.core.recording.shutil.disk_usage", lambda _: SimpleNamespace(free=0))
    with pytest.raises(OSError, match="disk"):
        archive.append(data, stamp(8))
    assert len(archive.rows) == 2
    archive.finish_capture("test disconnect")
    assert json.loads((archive.folder / "recording.json").read_text())["frames"] == 2


def test_encoder_arguments_timing_validation_and_recovery(tmp_path):
    archive = FrameArchive(tmp_path, profile="baseline", crf=20)
    archive.append(png(), stamp(10))
    archive.append(png(color="blue"), stamp(11.4))
    calls = []

    def runner(args, folder, cancelled, **kwargs):
        calls.append(args)
        if "-version" in args:
            return "ffmpeg offline fixture"
        if "-encoders" in args:
            return "libx264"
        if "-show_streams" in args:
            return json.dumps(
                {
                    "streams": [
                        {
                            "codec_type": "video",
                            "codec_name": "h264",
                            "width": 242,
                            "height": 322,
                            "nb_read_frames": "3",
                        }
                    ],
                    "format": {"duration": "2.44"},
                }
            )
        (folder / "video.partial.mp4").write_bytes(b"fixture, not a real video")
        return ""

    video = archive.encode("ffmpeg", "ffprobe", lambda: False, runner=runner)
    encode_call = next(args for args in calls if "-c:v" in args)
    assert encode_call[encode_call.index("-bf") + 1] == "0"
    assert video.name == "video.mp4" and archive.manifest["status"] == "complete"
    assert "duration 1.400000" in (archive.folder / "frames.ffconcat").read_text()
    assert "pad=ceil(iw/2)*2:ceil(ih/2)*2" in calls[2] and "-n" in calls[2]
    assert calls[2][calls[2].index("-profile:v") + 1] == "baseline"
    with pytest.raises(RecordingCancelled):
        archive.encode("ffmpeg", "ffprobe", lambda: True, runner=runner)
    assert video.exists()  # Earlier output was never replaced.


def test_missing_encoder_and_cancelled_process_leave_recoverable_frames(tmp_path):
    archive = FrameArchive(tmp_path)
    archive.append(png(), stamp(1))
    with pytest.raises(OSError):
        archive.encode(str(tmp_path / "missing-encoder.exe"), "missing-probe", lambda: False)
    assert not (archive.folder / "video.mp4").exists()
    assert (archive.folder / "frame-000000.png").exists()
    import sys

    checks = []

    def cancel_after_launch():
        checks.append(True)
        return len(checks) > 1

    with pytest.raises(RecordingCancelled):
        run_tool(
            [sys.executable, "-c", "import time; time.sleep(10)"],
            archive.folder,
            cancel_after_launch,
        )


def test_worker_recording_poll_override_restores_page_behavior(qtbot):
    worker = AcquisitionWorker()
    meter = MagicMock(spec=WebXiClient)
    meter.actions = set()
    meter.screen_image.return_value = png()
    worker.device, worker.mode = meter, "instrument"
    worker.command("screen", False)
    frames = []
    worker.recording_frame.connect(lambda data, timing: frames.append((data, timing)))
    worker.command("record_screen", True)
    worker.poll()
    assert len(frames) == 1 and frames[0][1]["monotonic"] > 0
    worker.command("record_screen", False)
    worker.poll()
    assert meter.screen_image.call_count == 1
    worker.disconnect()
    assert not worker.recording_screen


def test_recording_queue_bound_cancel_shutdown(qtbot, tmp_path):
    data = png()
    job = RecordingJob(tmp_path)
    for i in range(10):
        job.submit(data, stamp(i + 1))
    assert job.frames.qsize() == 8 and job.dropped == 1 and job.stop_capture.is_set()
    window = MainWindow(data_dir=tmp_path / "app")
    try:
        window.recording_panel.job = job
        job.finished.connect(window.recording_panel.finished)
        job.start()
        window.close()
        qtbot.waitUntil(lambda: window.thread_finished, timeout=5000)
        assert window.recording_panel.job is None
        folders = list(tmp_path.glob("BnKG-SLM-*"))
        assert len(folders) == 1
        assert json.loads((folders[0] / "recording.json").read_text())["status"] == "cancelled"
    finally:
        window.close()


def test_expired_or_changed_screen_acknowledgement_sends_no_write(qtbot):
    worker = AcquisitionWorker()
    meter = MagicMock(spec=WebXiClient)
    meter.actions = {"KeyUp"}
    meter.armed = True
    meter.uncertain = False
    worker.device = meter
    worker.screen_received, worker.screen_digest = time.monotonic(), "new"
    worker.command(
        "screen_context",
        {"confirmed": True, "digest": "old", "confirmed_at": time.monotonic()},
    )
    meter.navigate_measurement_screen.assert_not_called()
    assert meter.navigation_ready is False


def test_recording_job_drains_and_preserves_originals(qtbot, tmp_path):
    job = RecordingJob(tmp_path)
    data = png()
    job.submit(data, stamp(1))
    job.submit(data, stamp(3))
    job.stop("fixture disconnect")
    job.start()
    qtbot.waitUntil(lambda: job.isFinished(), timeout=5000)
    folder = next(tmp_path.glob("BnKG-SLM-*"))
    manifest = json.loads((folder / "recording.json").read_text())
    assert manifest["status"] == "originals saved" and manifest["frames"] == 2
    assert (folder / "frame-000001.png").read_bytes() == data


def test_probe_rejects_wrong_duration_and_keeps_partial(tmp_path):
    archive = FrameArchive(tmp_path)
    archive.append(png(), stamp(1))

    def runner(args, folder, cancelled, **kwargs):
        if "-version" in args:
            return "fixture"
        if "-encoders" in args:
            return "libx264"
        if "-show_streams" in args:
            return json.dumps(
                {
                    "streams": [
                        {
                            "codec_type": "video",
                            "codec_name": "h264",
                            "width": 242,
                            "height": 322,
                            "nb_read_frames": "2",
                        }
                    ],
                    "format": {"duration": "900"},
                }
            )
        (folder / "video.partial.mp4").write_bytes(b"invalid fixture video")
        return ""

    with pytest.raises(ValueError, match="validation"):
        archive.encode("fixture", "probe", lambda: False, runner=runner)
    assert (archive.folder / "video.partial.mp4").exists()
    assert not (archive.folder / "video.mp4").exists()


def test_recording_panel_start_stop_and_cross_page_status(qtbot, tmp_path, monkeypatch):
    window = MainWindow(data_dir=tmp_path / "app")
    panel = window.recording_panel
    monkeypatch.setattr(
        "bnkg.ui.recording.QFileDialog.getExistingDirectory",
        lambda *a: str(tmp_path / "recordings with spaces"),
    )
    try:
        panel.set_connected(True)  # Panel fixture only; acquisition stays disconnected.
        panel.start_recording()
        qtbot.waitUntil(lambda: panel.status.text().startswith("Recording originals:"))
        assert not window.recording_notice.isHidden()
        panel.submit(png(), stamp(1))
        qtbot.waitUntil(lambda: "1 frames" in panel.status.text())
        window.navigation.setCurrentRow(0)
        assert not window.recording_notice.isHidden()
        panel.stop()
        qtbot.waitUntil(lambda: panel.job is None)
        assert window.recording_notice.isHidden()
        assert "originals saved" in panel.status.text()
        assert window.worker.device is None
    finally:
        window.close()
        qtbot.waitUntil(lambda: window.thread_finished)


def test_one_hour_recording_limit_without_wall_clock_wait(tmp_path):
    archive = FrameArchive(tmp_path)
    data = png()
    archive.append(data, stamp(0))
    archive.append(data, stamp(3600))
    with pytest.raises(OSError, match="duration limit"):
        archive.append(data, stamp(3600.1))
    assert len(archive.rows) == 2
