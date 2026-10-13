import json
import sqlite3
import threading

import pytest
import requests
from PySide6.QtCore import QMetaObject, Qt
from PySide6.QtWidgets import QBoxLayout

from bnkg.core import discovery
from bnkg.core.device import DEMO_MODES, DemoDevice
from bnkg.core.webxi import STATE, WebXiClient, WebXiError
from bnkg.ui.window import MainWindow
from bnkg.ui.worker import AcquisitionWorker


@pytest.mark.parametrize("mode", DEMO_MODES)
def test_demo_modes_vary_and_remain_explicitly_synthetic(mode):
    demo = DemoDevice(mode, seed=17)
    samples = [demo.read() for _ in range(80)]
    assert len({s.values["LAF"] for s in samples}) > 60
    assert all(s.origin == "simulation" and s.quality == "synthetic" for s in samples)
    assert all(20 < s.values["LAF"] < 110 for s in samples)


def test_paused_and_stopped_demo_never_append_repeated_rows(qtbot, tmp_path):
    worker = AcquisitionWorker()
    seen, captured = [], []
    worker.sample.connect(seen.append)
    worker.captured.connect(captured.append)
    worker.command("demo", "Ambient")
    for _ in range(5):
        worker.poll()
    assert seen and not captured
    database = tmp_path / "log.sqlite"
    worker.command("log_start", str(database))
    for _ in range(12):
        worker.poll()
    assert len(captured) == 12
    worker.command("toggle")
    before = len(seen)
    for _ in range(12):
        worker.poll()
    assert len(seen) == before
    assert worker.store.count == 12
    worker.command("disconnect")
    for _ in range(5):
        worker.poll()
    assert worker.store is None and not worker.capturing
    with sqlite3.connect(database) as db:
        assert db.execute("SELECT count(*) FROM samples").fetchone()[0] == 12
        assert db.execute("SELECT value FROM metadata WHERE key='closed_utc'").fetchone()


def test_local_capture_stop_closes_log_but_live_view_continues(qtbot, tmp_path):
    worker = AcquisitionWorker()
    worker.command("demo", "Events")
    worker.command("log_start", str(tmp_path / "log.sqlite"))
    worker.poll()
    worker.command("capture_stop")
    seen, captured = [], []
    worker.sample.connect(seen.append)
    worker.captured.connect(captured.append)
    worker.poll()
    assert seen and not captured and worker.store is None
    worker.shutdown()


def test_ui_memory_limit_preserves_all_logged_samples(qtbot, tmp_path, monkeypatch):
    from dataclasses import replace

    import bnkg.ui.worker as worker_module

    class FixtureMeter(WebXiClient):
        def __init__(self, *args, **kwargs):
            super().__init__("fixture.local")
            self.demo = DemoDevice(seed=1)

        def identify(self):
            return {"HostName": "Offline fixture"}

        def read(self):
            return replace(self.demo.read(), origin="instrument", quality="test fixture")

    monkeypatch.setattr(worker_module, "WebXiClient", FixtureMeter)
    window = MainWindow(data_dir=tmp_path)
    try:
        window.select_source("connect", {"address": "fixture.local"})
        qtbot.waitUntil(lambda: window.latest is not None, timeout=5000)
        assert window.table.rowCount() == 0 and len(window.history) == 0
        window.record_limit.setValue(5)
        window.toggle_logging()
        qtbot.waitUntil(lambda: window.logging)
        for _ in range(15):
            QMetaObject.invokeMethod(window.worker, "poll", Qt.ConnectionType.QueuedConnection)
        qtbot.waitUntil(lambda: window.table.rowCount() == 5, timeout=5000)
        window.select_source("disconnect")
        qtbot.waitUntil(lambda: window.source_mode == "disconnected")
        assert not window.logging and not window.capturing
        assert window.table.rowCount() == 5 and len(window.history) == 5
        with sqlite3.connect(window.session_path) as db:
            assert db.execute("SELECT count(*) FROM samples").fetchone()[0] >= 15
    finally:
        window.close()
        qtbot.waitUntil(lambda: window.thread_finished, timeout=5000)


def test_screen_layout_navigation_and_theme_defaults(qtbot, tmp_path):
    # Windows offscreen Qt has no automatic font discovery; use the real UI font.
    from pathlib import Path

    from PySide6.QtGui import QFont, QFontDatabase
    from PySide6.QtWidgets import QApplication

    font = Path("C:/Windows/Fonts/segoeui.ttf")
    if font.is_file():
        QFontDatabase.addApplicationFont(str(font))
        QApplication.instance().setFont(QFont("Segoe UI", 10))
    window = MainWindow(data_dir=tmp_path)
    window.show()
    try:
        assert window.navigation.item(1).text() == "SLM screen"
        assert list(window.theme.buttons) == ["System", "Dark", "Light"]
        assert window.theme.currentText() == "Dark"
        assert window.color_theme.currentText() == "B&KG"
        window.navigation.setCurrentRow(1)
        window.resize(480, 1000)
        qtbot.wait(100)
        assert window.slm_screen.flow.direction() == QBoxLayout.Direction.TopToBottom
        assert window.mobile_navigation.isVisible()
        window.resize(1280, 900)
        qtbot.wait(100)
        assert window.slm_screen.flow.direction() == QBoxLayout.Direction.LeftToRight
        for theme in ("B&KG", "Colorful", "Blue", "Red", "Green"):
            window.color_theme.setCurrentText(theme)
            for appearance in ("System", "Dark", "Light"):
                window.theme.setCurrentText(appearance)
                assert window.settings.value("theme") == appearance
    finally:
        window.close()
        qtbot.waitUntil(lambda: window.thread_finished, timeout=5000)


@pytest.mark.parametrize(
    "subnet", ["0.0.0.0/0", "10.0.0.0/16", "8.8.8.0/24", "127.0.0.0/24", "::1/128", "bad"]
)
def test_subnet_search_rejects_broad_or_nonlocal_targets(subnet):
    with pytest.raises(ValueError):
        discovery.subnet_hosts(subnet)


def test_scan_cancel_and_result_collection(monkeypatch):
    calls = []

    def scan(address, cancel):
        calls.append(address)
        return discovery.DiscoveredDevice(address, "fixture", "SLM identified", "Subnet")

    monkeypatch.setattr(discovery, "_scan_host", scan)
    results = []
    discovery.scan_subnet("192.168.1.0/30", threading.Event(), results.append, lambda _: None)
    assert {r.address for r in results} == {"192.168.1.1", "192.168.1.2"}
    assert len(discovery.subnet_hosts("192.168.1.0/24")) == 254


class Reply:
    status_code = 200

    def __init__(self, value):
        self.value = value

    def __enter__(self):
        return self

    def __exit__(self, *_):
        pass

    def raise_for_status(self):
        pass

    def iter_content(self, chunk_size):
        yield json.dumps(self.value).encode()


class ActionSession:
    def __init__(self, before="Activated", after="Running", timeout=False):
        self.before, self.after = before, after
        self.puts = []
        self.timeout = timeout

    def get(self, url, **kwargs):
        assert url.endswith(STATE)
        return Reply(self.after if self.puts else self.before)

    def put(self, url, **kwargs):
        self.puts.append((url, kwargs))
        if self.timeout:
            raise requests.Timeout("ambiguous")
        return Reply(None)

    def close(self):
        pass


def control_client(session):
    client = WebXiClient("slm.local", session)
    client.actions = {"StartPause", "Stop"}
    return client


def test_controls_require_arming_and_supported_action():
    session = ActionSession()
    client = control_client(session)
    with pytest.raises(PermissionError):
        client.measurement_action("StartPause", confirmations=1)
    client.armed = True
    for action in ("ResetStart", "StartCalibration", "KeyMenu", "unknown"):
        with pytest.raises(PermissionError):
            client.measurement_action(action)
    assert not session.puts
    assert client.measurement_action("StartPause") == "Running"
    assert len(session.puts) == 1 and client.armed
    assert session.puts[0][1]["allow_redirects"] is False


def test_stop_requires_arming_and_readback_but_no_dialog_confirmation():
    session = ActionSession("Running", "ResultMeasured")
    client = control_client(session)
    client.armed = True
    assert client.measurement_action("Stop") == "ResultMeasured"
    assert len(session.puts) == 1 and client.armed


@pytest.mark.parametrize("timeout,after", [(True, "Running"), (False, "Activated")])
def test_ambiguous_toggle_disarms_and_never_retries(timeout, after):
    session = ActionSession(after=after, timeout=timeout)
    client = control_client(session)
    client.armed = True
    with pytest.raises(WebXiError, match="no retry"):
        client.measurement_action("StartPause", confirmations=1)
    assert client.uncertain and not client.armed
    client.armed = True
    with pytest.raises(PermissionError):
        client.measurement_action("StartPause", confirmations=1)
    assert len(session.puts) == 1
    client.refresh_control_state()
    assert not client.uncertain


def test_start_after_stop_uses_normal_startpause_not_reset():
    session = ActionSession("ResultMeasured", "Running")
    client = control_client(session)
    client.armed = True
    assert client.measurement_action("StartPause") == "Running"
    assert len(session.puts) == 1
    assert session.puts[0][1]["params"] == {"Action": "StartPause"}
    assert client.armed and not client.uncertain


@pytest.mark.parametrize("state", ["ResultLoaded", "Error", "Deactivated", "Initial", "unknown"])
def test_start_does_not_clear_loaded_or_unknown_results(state):
    session = ActionSession(state)
    client = control_client(session)
    client.armed = True
    with pytest.raises(PermissionError, match="No command was sent"):
        client.measurement_action("StartPause")
    assert not session.puts


@pytest.mark.parametrize("state", ["Activated", "ResultMeasured"])
def test_stop_when_already_stopped_is_noop(state):
    session = ActionSession(state)
    client = control_client(session)
    client.armed = True
    assert client.measurement_action("Stop") == state
    assert not session.puts and client.armed


@pytest.mark.parametrize(
    "action,states,expected",
    [
        ("StartPause", ["Stopping", "ResultMeasured", "ResultMeasured", "Running"], "Running"),
        ("StartPause", ["Running", "RampingDown", "Paused"], "Paused"),
        ("StartPause", ["RampingDown", "Paused", "Running"], "Running"),
        ("Stop", ["Paused", "Stopping"], "Stopping"),
    ],
)
def test_transitions_use_gets_without_repeating_put(monkeypatch, action, states, expected):
    from unittest.mock import Mock

    session = ActionSession()
    client = control_client(session)
    client.armed = True
    client.get = Mock(side_effect=states)
    monkeypatch.setattr("bnkg.core.webxi.time.sleep", lambda _: None)
    assert client.measurement_action(action) == expected
    assert len(session.puts) == 1 and client.armed


def test_persistent_transition_sends_no_toggle(monkeypatch):
    session = ActionSession("Stopping")
    client = control_client(session)
    client.armed = True
    monkeypatch.setattr("bnkg.core.webxi.time.sleep", lambda _: None)
    with pytest.raises(PermissionError, match="still finishing"):
        client.measurement_action("StartPause")
    assert not session.puts


def test_discovery_thread_cancels_and_window_closes(qtbot, tmp_path, monkeypatch):
    import bnkg.ui.discovery as ui_discovery

    def wait_for_cancel(cancel, emit, progress):
        cancel.wait(3)

    monkeypatch.setattr(ui_discovery, "discover_mdns", wait_for_cancel)
    window = MainWindow(data_dir=tmp_path)
    window.start_discovery(None)
    window.close()
    qtbot.waitUntil(lambda: window.thread_finished, timeout=5000)
    assert window.discovery is None and not window.thread.isRunning()


def test_identify_requires_support_arming_and_never_retries():
    session = ActionSession()
    client = WebXiClient("fixture.local", session)
    client.actions = {"Identify"}
    with pytest.raises(PermissionError):
        client.identify_display(confirmed=True)
    assert not session.puts
    client.armed = True
    with pytest.raises(PermissionError):
        client.identify_display()
    assert not session.puts
    client.identify_display(confirmed=True)
    assert len(session.puts) == 1 and session.puts[0][1]["params"]["Action"] == "Identify"
    uncertain = ActionSession(timeout=True)
    client = WebXiClient("fixture.local", uncertain)
    client.actions = {"Identify"}
    client.armed = True
    with pytest.raises(WebXiError, match="uncertain"):
        client.identify_display(confirmed=True)
    with pytest.raises(PermissionError):
        client.identify_display(confirmed=True)
    assert len(uncertain.puts) == 1 and not client.armed
