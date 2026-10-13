import time
from dataclasses import replace

import pytest
import requests
from PySide6.QtWidgets import QMessageBox

from bnkg.core.device import DemoDevice
from bnkg.core.location import coordinate_text
from bnkg.core.webxi import SETUP, STATE, WebXiClient, WebXiError
from bnkg.ui.location import LocationPanel
from bnkg.ui.worker import AcquisitionWorker


class Reply:
    status_code = 200

    def __enter__(self):
        return self

    def __exit__(self, *_):
        pass


class LocationSession:
    def __init__(self):
        self.puts = []
        self.values = {
            "MetadataAll": 1,
            "Metadata1Metadata": 1,
            "Metadata1Type": 0,
            "Metadata1Name": "GPS coordinates",
            "Metadata1Text": "old location",
        }
        self.definitions = {
            "Metadata1Text": {"Metadata": {"DataType": "String", "Flags": "ReportChange"}}
        }
        self.state = "Activated"
        self.timeout = False
        self.mismatch = False

    def put(self, url, **kwargs):
        self.puts.append((url, kwargs))
        if self.timeout:
            raise requests.Timeout()
        if not self.mismatch:
            self.values["Metadata1Text"] = kwargs["json"]
        return Reply()

    def close(self):
        pass


@pytest.fixture
def meter(monkeypatch):
    session = LocationSession()
    client = WebXiClient("fixture.local", session)

    def get(path, **options):
        if path == STATE:
            return session.state
        assert path == SETUP
        return session.definitions if options.get("metadata") else dict(session.values)

    monkeypatch.setattr(client, "get", get)
    return client, session


@pytest.mark.parametrize(
    "lat,lon",
    [(91, 0), (0, 181), (float("nan"), 0), (0, float("inf")), (True, 0), ("bad", 0), (None, 0)],
)
def test_coordinates_reject_invalid_or_missing_fix(lat, lon):
    with pytest.raises(ValueError):
        coordinate_text(lat, lon)


def test_location_transfer_is_one_reviewed_text_write(meter):
    client, session = meter
    client.armed = True
    preview = client.preview_location(1, "12.345678", "23.456789", "user-default")
    # UI cannot modify server-held target/value by altering its copy.
    preview["after"] = "tampered"
    audit = []
    result = client.write_location(
        preview["token"], confirmations=2, audit=lambda outcome, p: audit.append(outcome)
    )
    assert result["after"] == "12.345678, 23.456789"
    assert len(session.puts) == 1
    url, options = session.puts[0]
    assert url.endswith("/Setup/Metadata1Text") and options["json"] == result["after"]
    assert options["allow_redirects"] is False and audit == ["attempt", "verified"]
    with pytest.raises(PermissionError):
        client.write_location(preview["token"], confirmations=2, audit=lambda *a: None)
    assert len(session.puts) == 1


@pytest.mark.parametrize(
    "field,value", [("MetadataAll", 0), ("Metadata1Metadata", 0), ("Metadata1Type", 1)]
)
def test_location_never_auto_enables_or_changes_type(meter, field, value):
    client, session = meter
    session.values[field] = value
    with pytest.raises(PermissionError):
        client.preview_location(1, 6, 79)
    assert not session.puts


@pytest.mark.parametrize("flags", ["ReadOnly,ReportChange", None])
def test_location_respects_current_write_flags(meter, flags):
    client, session = meter
    if flags is None:
        session.definitions["Metadata1Text"]["Metadata"].pop("Flags")
    else:
        session.definitions["Metadata1Text"]["Metadata"]["Flags"] = flags
    with pytest.raises(PermissionError):
        client.preview_location(1, 6, 79)
    assert not session.puts


@pytest.mark.parametrize(
    "change", ["value", "name", "state", "expired", "token", "disarmed", "one-confirmation"]
)
def test_location_preview_guards_prevent_put(meter, change):
    client, session = meter
    client.armed = True
    preview = client.preview_location(1, 6, 79)
    token = preview["token"]
    confirmations = 2
    if change == "value":
        session.values["Metadata1Text"] = "changed"
    if change == "name":
        session.values["Metadata1Name"] = "Operator"
    if change == "state":
        session.state = "Running"
    if change == "expired":
        client.location_preview["created"] = time.monotonic() - 61
    if change == "token":
        token = "forged"
    if change == "disarmed":
        client.armed = False
    if change == "one-confirmation":
        confirmations = 1
    with pytest.raises(PermissionError):
        client.write_location(token, confirmations=confirmations, audit=lambda *a: None)
    assert not session.puts


@pytest.mark.parametrize("failure", ["timeout", "mismatch"])
def test_location_uncertainty_disarms_without_retry(meter, failure):
    client, session = meter
    client.armed = True
    setattr(session, failure, True)
    preview = client.preview_location(1, 6, 79)
    with pytest.raises(WebXiError, match="uncertain"):
        client.write_location(preview["token"], confirmations=2, audit=lambda *a: None)
    assert len(session.puts) == 1 and client.uncertain and not client.armed
    with pytest.raises(PermissionError):
        client.preview_location(1, 6, 79)


def test_location_audit_failure_blocks_write(meter):
    client, session = meter
    client.armed = True
    preview = client.preview_location(1, 6, 79)

    def audit(*args):
        raise OSError("disk full")

    with pytest.raises(OSError):
        client.write_location(preview["token"], confirmations=2, audit=audit)
    assert not session.puts


def test_location_panel_default_and_missing_slm_fix(qtbot):
    panel = LocationPanel()
    qtbot.addWidget(panel)
    assert panel.latitude.text() == "" and panel.longitude.text() == ""
    assert panel.source == "manual" and not panel.preview.isEnabled()
    sample = replace(
        DemoDevice().read(),
        origin="instrument",
        metadata={"Latitude": {"value": None}, "Longitude": {"value": None}},
    )
    panel.update_sample(sample)
    panel.copy_slm()
    assert panel.latitude.text() == "" and "No usable" in panel.info.text()
    sample = replace(sample, metadata={"Latitude": {"value": 6.1}, "Longitude": {"value": 79.1}})
    panel.update_sample(sample)
    panel.copy_slm()
    assert panel.source == "slm-reported" and panel.latitude.text() == "6.100000"
    panel.clear_instrument()
    assert not panel.preview.isEnabled()


def test_location_cancel_has_no_write_command(qtbot, monkeypatch):
    panel = LocationPanel()
    qtbot.addWidget(panel)
    panel.armed = True
    monkeypatch.setattr(QMessageBox, "question", lambda *a: QMessageBox.StandardButton.No)
    commands = []
    panel.command.connect(lambda name, value: commands.append(name))
    panel.confirm_preview(
        {
            "address": "fixture.local",
            "slot": 1,
            "name": "GPS",
            "before": "old",
            "after": "6,79",
            "source": "manual",
        }
    )
    assert commands == [] and "cancelled" in panel.info.text()


def test_location_audit_saved_independently_of_measurement_logging(tmp_path):
    worker = AcquisitionWorker(audit_dir=tmp_path)
    worker.audit_location("attempt", {"slot": 1, "before": "old", "after": "6,79", "created": 1})
    text = (tmp_path / "BnKG-Location-Writes.jsonl").read_text()
    assert "location-text-metadata" in text and "created" not in text and worker.store is None
