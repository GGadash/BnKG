import json
import time
from dataclasses import replace

import pytest
from PySide6.QtCore import QBuffer, QIODevice
from PySide6.QtGui import QColor, QImage
from PySide6.QtWidgets import QApplication, QWidget

from bnkg.core.device import DemoDevice
from bnkg.core.export import export_session
from bnkg.core.measurements import band_centres, decode_outputs, level, metadata_snapshot
from bnkg.core.sessions import SessionStore
from bnkg.core.webxi import OUTPUTS, SEQUENCES, SETUP, STATE, WebXiClient, WebXiError
from bnkg.ui.about import KOFI, AboutPage
from bnkg.ui.components import ScreenPane

DESC = {"Name": "LAF", "DataType": "Int16", "Scale": 0.01, "Unit": "dB re 20uPa"}
CPB = {
    **DESC,
    "Name": "CPBLZF",
    "PeriodTime": 1073741824,
    "DataAxisType": "CPB",
    "DataAxisCpbBaseSystem": 10,
    "DataAxisCpbNumberFractions": 3,
    "VectorLength": 36,
    "DataAxisCpbFirstBand": 8,
}


@pytest.mark.parametrize("raw", [-32768, None, True, float("inf"), -1.7976931348623157e308, "6450"])
def test_invalid_levels_do_not_become_decibels(raw):
    assert level(raw, DESC) is None


def test_device_scaling_axis_slots_and_spectrum_mismatch():
    assert level(6425, DESC) == 64.25
    assert level(6425, {**DESC, "Scale": 0.1, "Offset": -3}) == 639.5
    assert level(6425, {**DESC, "IsPower": True}) is None
    freq = band_centres(CPB)
    assert (
        len(freq) == 36
        and freq[0] == pytest.approx(6.309573)
        and freq[-1] == pytest.approx(19952.62315)
    )
    assert band_centres({**CPB, "DataAxisCpbBaseSystem": 2}) == []
    octave = band_centres(
        {**CPB, "DataAxisCpbNumberFractions": 1, "VectorLength": 11, "DataAxisCpbFirstBand": 12}
    )
    assert octave[0] == pytest.approx(15.84893) and octave[-1] == pytest.approx(15848.93)
    seq = {"LAF": DESC, "LN3": DESC, "CPBLZF": CPB}
    values, spectra = decode_outputs(
        {"LAF": 6100, "LN3": 5500, "CPBLZF250ms": [1000] * 36}, seq, {"StatisticsPercentile3": 10}
    )
    assert values["L10"] == 55 and "L50" not in values
    assert spectra["CPBLZF250ms"]["values"] == [10] * 36
    assert decode_outputs({"CPBLZF250ms": [1000] * 33}, seq, {})[1] == {}


def test_metadata_missing_gps_and_access_flags():
    fields = metadata_snapshot(
        {"Latitude": -1.7976931348623157e308},
        {"Metadata1Name": "Operator", "UnrelatedPrivateSetting": "omit"},
        {"Metadata1Name": {"Metadata": {"Flags": "ReadOnly"}}},
    )
    assert fields["Latitude"]["value"] is None
    assert fields["Metadata1Name"]["access"] == "Read-only on device"
    assert "UnrelatedPrivateSetting" not in fields


def test_acquisition_has_no_writes_and_rejects_mid_read_setup_change(monkeypatch):
    client = WebXiClient("fixture.local")
    calls = []
    changing = False

    def get(path, **options):
        calls.append(path)
        if path == STATE:
            return "Activated"
        if path == SEQUENCES:
            return {"SLM": {"Fast": {"1": DESC}}}
        if path == OUTPUTS:
            return {"LAF": 4225, "Latitude": -1.7976931348623157e308}
        if path == SETUP:
            if options.get("metadata"):
                return {}
            return {"FrequencyRange": 1 if not changing or calls.count(SETUP) == 1 else 0}
        raise AssertionError(path)

    monkeypatch.setattr(client, "get", get)
    sample = client.read()
    assert sample.values["LAF"] == 42.25 and sample.metadata["Latitude"]["value"] is None
    assert sample.raw_values["_hbkg_context"]["sequences"]["LAF"] == DESC
    changing = True
    calls.clear()
    with pytest.raises(WebXiError, match="setup changed"):
        client.read()
    client.close()


def test_screen_keeps_native_bytes_dims_and_marks_timeout(qtbot, tmp_path):
    screen = ScreenPane(QWidget())
    qtbot.addWidget(screen)
    image = QImage(240, 320, QImage.Format.Format_RGB32)
    image.fill(QColor("green"))
    buffer = QBuffer()
    buffer.open(QIODevice.OpenModeFlag.WriteOnly)
    image.save(buffer, "PNG")
    png = bytes(buffer.data())
    screen.set_image(png)
    screen.set_status("Live SLM display")
    screen.set_status("Disconnected — no SLM connected")
    assert not screen.pixmap.isNull() and screen.png == png and screen.opacity.opacity() < 1
    assert screen.pixmap.width() == 240 and screen.pixmap.height() == 320
    path = tmp_path / "native.png"
    screen.save_png(path)
    assert path.read_bytes() == png
    with pytest.raises(FileExistsError):
        screen.save_png(path)
    screen.set_status("Live SLM display")
    screen.received_at = time.monotonic() - 8
    screen.check_age()
    assert "not updating" in screen.status.text()
    screen.received_at = time.monotonic()
    screen.changed_at = time.monotonic() - 40
    screen.check_age()
    assert "may be off" in screen.status.text()


def test_about_copy_feedback(qtbot):
    about = AboutPage("Independent application")
    qtbot.addWidget(about)
    about.copy_link(KOFI)
    assert QApplication.clipboard().text() == "https://ko-fi.com/gadash"
    assert about.feedback.text() == "Link copied to clipboard"


def test_descriptor_context_survives_session_json_export(tmp_path):
    sample = replace(
        DemoDevice().read(),
        origin="instrument",
        values={"LAF": 61.25},
        raw_values={"LAF": 6125, "_hbkg_context": {"sequences": {"LAF": DESC}}},
        descriptors={"LAF": DESC},
    )
    db = tmp_path / "session.sqlite"
    store = SessionStore(db, "instrument")
    store.append(sample)
    store.close()
    out = tmp_path / "out.json"
    export_session(db, out, "json")
    document = json.loads(out.read_text())
    assert "parameter_basis" in document["session"]
    assert (
        document["samples"][0]["raw_values"]["_hbkg_context"]["sequences"]["LAF"]["Scale"] == 0.01
    )


def test_frequency_label_tracks_instrument_bandwidth_change(qtbot):
    from bnkg.ui.live_views import FrequencyPage

    page = FrequencyPage()
    qtbot.addWidget(page)
    spectrum = {
        "frequencies": [1000],
        "values": [60],
        "origin": "instrument",
        "descriptor": {"DataAxisCpbNumberFractions": 3},
    }
    page.update_spectra({"CPBLZF250ms": spectrum})
    assert "1/3 octave" in page.selector.currentText()
    spectrum = {**spectrum, "descriptor": {"DataAxisCpbNumberFractions": 1}}
    page.update_spectra({"CPBLZF250ms": spectrum})
    assert "1/1 octave" in page.selector.currentText()
    assert page.selector.currentData() == "CPBLZF250ms"


def test_health_metadata_preserves_units_enums_and_rejects_unknown_groups():
    from bnkg.core.measurements import device_health_fields, metadata_text

    defs = {
        "Charged": {"Metadata": {"Flags": "ReadOnly", "DisplayHint": "%"}},
        "Status": {
            "Metadata": {
                "Flags": "ReadOnly",
                "Domain": {"List": {"Values": [2], "Names": ["Discharging"]}},
            }
        },
        "Unknown": {"Metadata": {}},
    }
    fields = device_health_fields(
        {"Charged": 39, "Status": 2, "Unknown": 123}, defs, "Battery", "2026-09-20T00:00:00Z"
    )
    assert metadata_text(fields["Device.Battery.Charged"]) == "39 %"
    assert metadata_text(fields["Device.Battery.Status"]) == "2 (Discharging)"
    assert fields["Device.Battery.Charged"]["raw"] == 39
    assert "Device.Battery.Unknown" not in fields
    with pytest.raises(ValueError):
        device_health_fields({}, {}, "Access", "now")


def test_optional_health_failure_does_not_stop_measurement(monkeypatch):
    client = WebXiClient("fixture.local")
    client.health_groups = {"Battery"}

    def get(path, **options):
        if path == STATE:
            return "Activated"
        if path == SEQUENCES:
            return {"SLM": {"1": DESC}}
        if path == SETUP:
            return {}
        if path == OUTPUTS:
            return {"LAF": 4250}
        raise WebXiError("Unavailable status")

    monkeypatch.setattr(client, "get", get)
    sample = client.read()
    assert sample.values["LAF"] == 42.5
    assert sample.metadata["Device.Battery"]["value"] is None
    client.close()


def test_unknown_setup_access_is_not_advertised_as_writable():
    fields = metadata_snapshot({}, {"Metadata1Name": "Operator"}, {})
    assert fields["Metadata1Name"]["access"] == "Access unknown; no writes allowed"
