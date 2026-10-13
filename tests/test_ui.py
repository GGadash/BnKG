import csv
from dataclasses import replace

from bnkg.core.device import DemoDevice
from bnkg.ui.window import MainWindow


def test_demo_isolated_simple_save_and_clean_shutdown(qtbot, tmp_path, monkeypatch):
    window = MainWindow(data_dir=tmp_path, demo=True)
    window.show()
    try:
        qtbot.waitUntil(lambda: window.demo_page.latest is not None, timeout=5000)
        demo = window.demo_page
        assert window.latest is None and window.source_mode == "disconnected"
        assert not window.logging and window.table.rowCount() == 0
        assert window.tiles["LAF"].value.text() == "—"
        assert "SYNTHETIC" in demo.readings.text()
        path = tmp_path / "demo.csv"
        monkeypatch.setattr(
            "bnkg.ui.live_views.QFileDialog.getSaveFileName", lambda *a: (str(path), "CSV")
        )
        demo.toggle_save()
        for _ in range(105):
            demo.poll()
        assert demo.table.rowCount() == 100
        demo.toggle_pause()
        before = path.read_bytes()
        demo.poll()
        assert path.read_bytes() == before
        demo.stop()
        demo.poll()
        assert path.read_bytes() == before
        with path.open() as handle:
            assert len(list(csv.reader(handle))) == 106
        assert not window.session_path and not window.history
        window.theme.setCurrentText("Light")
        assert window.theme.currentText() == "Light"
    finally:
        window.close()
        qtbot.waitUntil(lambda: window.thread_finished, timeout=5000)
    assert not window.thread.isRunning()


def test_stale_status_clears_instrument_readings(qtbot, tmp_path):
    window = MainWindow(data_dir=tmp_path)
    try:
        window.receive_sample(replace(DemoDevice().read(), origin="instrument"))
        assert window.tiles["LAF"].value.text() != "—"
        window.receive_status("stale", "connection lost")
        assert window.tiles["LAF"].value.text() == "—"
        assert "STALE" in window.origin_banner.text()
        assert not window.frequency_page.spectra
        assert not window.metadata_page.fields
    finally:
        window.close()
        qtbot.waitUntil(lambda: window.thread_finished, timeout=5000)
