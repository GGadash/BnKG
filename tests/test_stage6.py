import json
import sqlite3
from dataclasses import replace
from datetime import UTC, datetime
from unittest.mock import MagicMock

import pytest
import requests
from openpyxl import load_workbook
from PySide6.QtCore import QSettings, Qt
from PySide6.QtWidgets import QApplication

from bnkg.core.device import DemoDevice
from bnkg.core.export import export_session
from bnkg.core.report_context import log_filename, validate_context
from bnkg.core.sessions import SessionStore
from bnkg.core.webxi import ROOT, WebXiClient, WebXiError
from bnkg.ui.diagnostics import ConnectionDiagnostics
from bnkg.ui.live_views import MetadataPage
from bnkg.ui.location import LocationPanel
from bnkg.ui.window import MainWindow
from bnkg.ui.worker import AcquisitionWorker


def test_local_context_is_snapshotted_and_survives_metadata_exports(tmp_path):
    context = {
        "project": "=unsafe formula",
        "operator": "Operator example",
        "site": "Site",
        "notes": '<script>alert("x")</script>',
    }
    worker = AcquisitionWorker()
    worker.device = MagicMock(spec=WebXiClient)
    worker.device.session = MagicMock()
    worker.mode = "instrument"
    path = tmp_path / "local.sqlite"
    worker.command("log_start", {"path": str(path), "report_context": context})
    assert worker.store is not None
    context["project"] = "Edited future draft"
    worker.store.append(replace(DemoDevice().read(), origin="instrument"))
    worker.command("log_stop")
    worker.device.session.put.assert_not_called()
    with sqlite3.connect(path) as db:
        metadata = dict(db.execute("SELECT key,value FROM metadata"))
    assert metadata["local_report.project"] == "=unsafe formula"
    assert "not instrument" in metadata["local_report.source"]
    for fmt in ("json", "xlsx", "html"):
        target = tmp_path / ("export." + fmt)
        assert export_session(path, target, fmt) == 1
    data = json.loads((tmp_path / "export.json").read_text())
    assert data["session"]["local_report.operator"] == "Operator example"
    book = load_workbook(tmp_path / "export.xlsx", read_only=True)
    summary = dict(list(book["Summary"].values)[1:])
    assert summary["local_report.project"] == "'=unsafe formula"
    book.close()
    html = (tmp_path / "export.html").read_text()
    assert "&lt;script&gt;" in html and "<script>alert" not in html


def test_context_validation_and_safe_filename(tmp_path):
    name = log_filename(
        {"project": "../../CON:example", "site": "a/b\\c"}, True, datetime(2026, 9, 29, tzinfo=UTC)
    )
    assert "/" not in name and "\\" not in name and ":" not in name
    assert name.startswith("BnKG-LocalLog-instrument-") and name.endswith("Z.sqlite")
    for invalid in (
        {"Latitude": 4},
        {"notes": "x" * 2001},
        {"project": {"value": "x"}},
        {"site": "a\x00b"},
    ):
        with pytest.raises(ValueError):
            SessionStore(tmp_path / "must-not-exist.sqlite", "instrument", report_context=invalid)
        assert not (tmp_path / "must-not-exist.sqlite").exists()
    assert validate_context({}) == {"project": "", "operator": "", "site": "", "notes": ""}


def test_diagnostics_allowlist_and_stale_identity(qtbot):
    panel = ConnectionDiagnostics()
    qtbot.addWidget(panel)
    panel.remember(
        "http://private-meter.local",
        {
            "HostName": "PRIVATE",
            "Id": "SERIAL",
            "Type": "2255",
            "Version": {"Firmware": "fixture", "password": "secret"},
            "Access": {"Challenge": "secret"},
            "password": "secret",
        },
    )
    panel.set_mode("instrument")
    panel.set_controls(True, ["StartPause", "Calibration", "secret"])
    panel.sample_seen(
        replace(
            DemoDevice().read(), origin="instrument", metadata={"password": {"value": "secret"}}
        )
    )
    report = panel.support_summary()
    assert "PRIVATE" not in report and "private-meter" not in report and "SERIAL" not in report
    assert "secret" not in report and "Calibration" not in report
    panel.private.setChecked(True)
    assert "PRIVATE" in panel.support_summary() and "secret" not in panel.support_summary()
    panel.set_mode("disconnected")
    assert not panel.armed and panel.last_sample is None and not panel.actions
    assert panel.table.item(0, 1).text() == "Retained / not live"
    panel.copy_summary()
    assert json.loads(QApplication.clipboard().text())["connection_state"] == "disconnected"
    for _ in range(40):
        panel.set_mode("connecting")
        panel.set_mode("disconnected")
    assert len(panel.events) == 32 and panel.identity == {}


def test_metadata_filters_keep_selection_and_local_draft_independent(qtbot, tmp_path):
    settings = QSettings(str(tmp_path / "prefs.ini"), QSettings.Format.IniFormat)
    page = MetadataPage(settings)
    qtbot.addWidget(page)
    commands = []
    page.location.command.connect(lambda *args: commands.append(args))
    fields = {
        "Latitude": {"value": 0, "access": "Read-only output"},
        "Metadata1Text": {
            "value": "Site A",
            "access": "Device advertises writable; use physical SLM",
        },
        "Device.Battery.Level": {"value": 45, "access": "Read-only device status"},
    }
    page.update_fields(fields)
    page.group.setCurrentText("SLM metadata slots")
    visible = [r for r in range(page.table.rowCount()) if not page.table.isRowHidden(r)]
    assert len(visible) == 1
    page.table.item(visible[0], 0).setCheckState(Qt.CheckState.Checked)
    page.search.setText("missing")
    assert all(page.table.isRowHidden(r) for r in range(page.table.rowCount()))
    assert "Metadata1Text" in page.selected
    page.report.fields["project"].setText("Local project")
    page.report.save_draft()
    page.update_fields({})
    assert page.report.values()["project"] == "Local project" and not commands
    assert settings.value("report_project") == "Local project"
    assert fields["Metadata1Text"]["value"] == "Site A"


@pytest.mark.parametrize(
    "kind,expected",
    [
        ("timeout", "timed out"),
        ("connection", "Cannot reach"),
        ("tls", "TLS"),
        ("403", "access denied"),
        ("404", "endpoint unavailable"),
    ],
)
def test_transport_errors_are_actionable_without_credentials(kind, expected):
    session = MagicMock()
    response = requests.Response()
    response.status_code = int(kind) if kind.isdigit() else 500
    errors = {
        "timeout": requests.Timeout("password=secret"),
        "connection": requests.ConnectionError("password=secret"),
        "tls": requests.exceptions.SSLError("password=secret"),
    }
    session.get.side_effect = errors.get(
        kind, requests.HTTPError("password=secret", response=response)
    )
    client = WebXiClient("fixture.local", session=session, password="secret")
    with pytest.raises(WebXiError) as exc:
        client.get(ROOT)
    assert expected in str(exc.value) and "secret" not in str(exc.value)
    assert session.get.call_count == 1
    session.put.assert_not_called()


def test_location_map_is_explicit_and_provenance_preserved(qtbot):
    panel = LocationPanel()
    qtbot.addWidget(panel)
    commands = []
    panel.command.connect(lambda *args: commands.append(args))
    assert not panel.copy_map.isEnabled() and "unavailable" in panel.map_link.text()
    panel.latitude.setText("0")
    panel.longitude.setText("0")
    panel.copy_map.click()
    assert "mlat=0.000000" in QApplication.clipboard().text()
    panel.latitude.setText("invalid")
    assert not panel.copy_map.isEnabled() and not panel.map_url and not commands


def test_log_request_copies_local_draft_without_connecting(qtbot, tmp_path, monkeypatch):
    monkeypatch.setattr(
        WebXiClient, "identify", lambda _: pytest.fail("Unexpected network connection")
    )
    window = MainWindow(data_dir=tmp_path)
    try:
        window.command_requested.disconnect(window.worker.command)
        calls = []
        window.command_requested.connect(lambda name, value: calls.append((name, value)))
        window.metadata_page.report.fields["project"].setText("New project")
        window.metadata_page.report.naming.setCurrentIndex(1)
        window.source_mode = "instrument"  # UI-only fixture; acquisition stays disconnected.
        window.toggle_logging()
        name, options = calls[-1]
        assert name == "log_start" and "New-project" in options["path"]
        window.metadata_page.report.fields["project"].setText("Later draft")
        assert options["report_context"]["project"] == "New project"
        assert window.worker.device is None
        window.latest = replace(DemoDevice().read(), origin="instrument")
        window.receive_status("disconnected", "Fixture ended")
        assert window.latest is None
        assert window.device_info.text().startswith("DISCONNECTED")
    finally:
        window.close()
        qtbot.waitUntil(lambda: window.thread_finished)
