"""Focused acceptance for scope, provenance, isolation and display preferences."""

import json
from copy import deepcopy
from dataclasses import replace

from PySide6.QtCore import QSettings

from bnkg.core.device import DemoDevice
from bnkg.core.spectrum import SpectrumFrame, spectrum_meaning
from bnkg.ui.frequency import FrequencyPage
from bnkg.ui.preferences import PreferencesDialog
from bnkg.ui.presentation import Page
from bnkg.ui.window import MainWindow


def spectrum(weight="Z", total=False, interval=None):
    quantity = "L" + weight + ("eq" if total else "F")
    item = {
        "origin": "instrument",
        "frequencies": [100, 1000, 10000],
        "values": [-5, 0, None],
        "descriptor": {
            "LocalName": quantity,
            "AcousticalWeighting": weight,
            "FunctionType": "OctaveLeq" if total else "OctaveL",
            "AveragingMode": "Linear" if total else "Fast",
            "Unit": "dB re 20uPa",
            "PeriodTime": 4294967296 if total else 1073741824,
            "DataAxisCpbNumberFractions": 3,
        },
    }
    if interval is not None:
        item.update(integration_interval_ms=interval, integration_basis="Verified interval fixture")
    return "CPB" + quantity + ("" if total else "250ms"), item


def test_measurement_scope_never_inferred_from_fast_or_output_period():
    key, current = spectrum()
    meaning = spectrum_meaning(key, current)
    assert meaning.kind == "current" and meaning.period_ms is None
    assert meaning.output_ms == 250 and "250 ms output" in meaning.label
    key, total = spectrum(total=True)
    assert spectrum_meaning(key, total).kind == "total"
    assert spectrum_meaning(key, total).period_ms is None
    key, interval = spectrum(total=True, interval=125)
    assert spectrum_meaning(key, interval).kind == "interval"
    assert "125 ms interval Leq" in spectrum_meaning(key, interval).label
    interval.pop("integration_basis")
    assert spectrum_meaning(key, interval).kind == "total"
    key, unknown = spectrum()
    unknown["descriptor"].pop("FunctionType")
    assert spectrum_meaning(key, unknown).kind == "unknown"
    key, conflict = spectrum()
    conflict["descriptor"]["AcousticalWeighting"] = "A"
    assert spectrum_meaning(key, conflict).kind == "unknown"


def test_snapshot_copies_axes_descriptors_values_and_measurement_identity():
    key, item = spectrum()
    metadata = {
        "MeasurementCounter": {"value": 42},
        "ElapsedTime": {"raw": float("nan"), "value": None},
    }
    frame = SpectrumFrame.capture({key: item}, broadband={"LZF": 60}, measurement=metadata)
    item["values"][0] = 99
    item["descriptor"]["LocalName"] = "wrong"
    metadata["MeasurementCounter"]["value"] = 43
    assert frame.series[0].values == (-5, 0, None)
    assert frame.series[0].descriptor["LocalName"] == "LZF"
    assert json.loads(frame.measurement_json)["MeasurementCounter"]["value"] == 42
    copy = frame.series[0].as_dict()
    copy["frequencies"][0] = 1
    assert frame.series[0].frequencies[0] == 100


def test_only_compatible_series_compared_and_no_missing_weight_synthesized(qtbot):
    page = FrequencyPage()
    qtbot.addWidget(page)
    data = dict([spectrum(), spectrum("A"), spectrum("Z", total=True)])
    page.update_spectra(data, broadband={"LZF": 63, "LAF": 59, "LZeq": 57})
    assert {s.meaning.quantity for s in page.visible_series} == {"LZF", "LAF"}
    assert not page.weight_checks["C"].isEnabled()
    assert "LZeq" not in page.totals.text() and "63.00" in page.totals.text()
    different = deepcopy(data)
    different["CPBLAF250ms"]["frequencies"] = [125, 1000, 10000]
    page.update_spectra(different)
    assert len(page.visible_series) == 1
    different = deepcopy(data)
    different["CPBLAF250ms"]["descriptor"]["PeriodTime"] = 4294967296
    page.update_spectra(different)
    assert len(page.visible_series) == 1
    page.scope.setCurrentIndex(page.scope.findData("total"))
    assert len(page.visible_series) == 1 and page.visible_series[0].meaning.kind == "total"


def test_frozen_source_survives_updates_disconnect_and_scope_change(qtbot):
    page = FrequencyPage()
    qtbot.addWidget(page)
    data = dict([spectrum(), spectrum("A", total=True)])
    page.update_spectra(data, broadband={"LZF": 52, "LAeq": 55}, timestamp="original")
    page.freeze_current()
    page.scope.setCurrentIndex(page.scope.findData("total"))
    page.update_spectra({}, timestamp="new")
    assert page.frame.timestamp == "original"
    assert "55.00" in page.totals.text()
    assert "FROZEN" in page.notice.text()
    assert page.frame.series and not page.live_frame.series
    page.source.setCurrentIndex(0)
    assert not page.spectra and page.table.rowCount() == 0


def test_interval_totals_do_not_borrow_cumulative_broadband(qtbot):
    page = FrequencyPage()
    qtbot.addWidget(page)
    page.update_spectra(dict([spectrum(total=True, interval=125)]), broadband={"LZeq": 73})
    assert "73" not in page.totals.text() and "unavailable" in page.totals.text()
    assert "125 ms interval" in page.notice.text()
    assert page.table.item(0, 2).text() == "-5.00"
    assert page.table.item(1, 2).text() == "0.00"
    assert page.table.item(2, 2).text() == "—"


def test_display_preferences_persist_without_acquisition(qtbot, tmp_path):
    settings = QSettings(str(tmp_path / "preferences.ini"), QSettings.Format.IniFormat)
    dialog = PreferencesDialog(settings)
    qtbot.addWidget(dialog)
    dialog.font_size.setValue(34)
    dialog.density.setCurrentText("Compact")
    dialog.spectrum.setChecked(True)
    dialog.save(settings)
    settings.sync()
    window = MainWindow(data_dir=tmp_path)
    try:
        assert window.latest is None and window.source_mode == "disconnected"
        assert window.settings.value("reading_font_size", type=int) == 34
        assert not window.spectrum_preview.isHidden()
        assert window.tiles["LAF"].minimumHeight() == 92
        assert window.pages.widget(Page.FREQUENCY) is window.frequency_page
        assert window.navigation.item(Page.SLM).text() == "SLM screen"
        assert window.settings.value("color_theme") == "B&KG"
        # Instrument views reject synthetic input, even when it has matching spectra.
        sample = replace(DemoDevice().read(), spectra=dict([spectrum()]))
        window.receive_sample(sample)
        assert window.latest is None and not window.frequency_page.live_frame.series
    finally:
        window.close()
        qtbot.waitUntil(lambda: window.thread_finished, timeout=5000)


def test_demo_event_is_repeatable_and_bounded():
    first, second = DemoDevice("Ambient", seed=7), DemoDevice("Ambient", seed=7)
    first.inject_event()
    for step in range(7):
        a, b = first.read(), second.read()
        assert abs(a.values["LAF"] - b.values["LAF"] - max(0, 18 - step * 3)) < 1e-9
        assert a.origin == "simulation"


def test_frequency_narrow_controls_and_demo_pause_are_explicit(qtbot):
    # Qt's Windows offscreen plugin does not discover installed fonts automatically.
    from pathlib import Path

    from PySide6.QtGui import QFont, QFontDatabase

    from bnkg.ui.live_views import DemoPage

    font_path = Path("C:/Windows/Fonts/segoeui.ttf")
    if font_path.exists():
        QFontDatabase.addApplicationFont(str(font_path))
    demo = DemoPage()
    demo.setFont(QFont("Segoe UI", 10))
    qtbot.addWidget(demo)
    demo.toggle()
    demo.timer.stop()
    try:
        page = demo.frequency
        page.resize(440, 880)
        assert page.minimumSizeHint().width() <= 440
        assert len(page.visible_series) == 3
        assert all(s.origin == "simulation" for s in page.visible_series)
        demo.toggle_pause()
        assert "paused" in page.notice.text()
        demo.stop()
        assert "stopped" in page.notice.text()
        assert demo.tabs.count() == 2
    finally:
        demo.stop()
