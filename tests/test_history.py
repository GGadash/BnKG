import hashlib
import json
import sqlite3
import threading
from dataclasses import replace

import pytest

from bnkg.core.device import DemoDevice
from bnkg.core.history import read_page, read_sample
from bnkg.core.sessions import SessionStore
from bnkg.ui.presentation import Page
from bnkg.ui.window import MainWindow

DESC = {
    "Name": "CPBLZF",
    "LocalName": "LZF",
    "FunctionType": "OctaveL",
    "AveragingMode": "Fast",
    "AcousticalWeighting": "Z",
    "DataType": "Int16",
    "Scale": 0.01,
    "Unit": "dB re 20uPa",
    "PeriodTime": 1073741824,
    "DataAxisType": "CPB",
    "DataAxisCpbBaseSystem": 10,
    "VectorLength": 3,
    "DataAxisCpbFirstBand": 28,
    "DataAxisCpbNumberFractions": 3,
}
SCALAR = {"Name": "LZF", "DataType": "Int16", "Scale": 0.01, "Unit": "dB re 20uPa"}


def create_log(path, count=1, origin="instrument", context=True, close=True):
    store = SessionStore(path, origin)
    sample = replace(
        DemoDevice(seed=7).read(),
        origin=origin,
        values={"LAF": 60, "LZF": 62},
        raw_values={
            "CPBLZF250ms": [-500, 0, -32768],
            "LZF": 6200,
            **(
                {
                    "_hbkg_context": {
                        "sequences": {"CPBLZF": DESC, "LZF": SCALAR},
                        "setup_basis": {},
                        "metadata": {"MeasurementCounter": {"value": 5}},
                    }
                }
                if context
                else {}
            ),
        },
    )
    for _ in range(count):
        store.append(sample)
    if close:
        store.close()
    return store, sample


def test_read_only_pages_stable_ceiling_and_legacy_rows(tmp_path):
    path = tmp_path / "saved #1.sqlite"
    store, sample = create_log(path, 205, close=False)
    first = read_page(path)
    assert len(first.rows) == 100 and not first.previous and first.following
    store.append(sample)
    middle = read_page(path, after=100, ceiling=first.ceiling)
    last = read_page(path, after=200, ceiling=first.ceiling)
    assert len(last.rows) == 5 and not last.following
    assert read_page(path, before=201, ceiling=first.ceiling).rows == middle.rows
    assert read_page(path).ceiling == 206
    store.close()
    before = hashlib.sha256(path.read_bytes()).hexdigest()
    result = read_sample(path, 1)
    assert result.frame.series[0].values == (-5, 0, None)
    assert dict(result.frame.broadband)["LZF"] == 62
    assert result.frame.series[0].meaning.kind == "current"
    assert result.frame.series[0].meaning.period_ms is None
    assert "5" in result.frame.measurement_json
    assert hashlib.sha256(path.read_bytes()).hexdigest() == before
    old = tmp_path / "legacy.sqlite"
    create_log(old, context=False)
    assert read_page(old).rows[0].laf == 60
    assert read_sample(old, 1).frame is None


@pytest.mark.parametrize(
    "mode",
    ["missing", "corrupt", "version", "view", "json", "oversized", "context", "identity", "cancel"],
)
def test_bad_history_fails_without_modifying_source(tmp_path, mode):
    path = tmp_path / "bad.sqlite"
    if mode == "missing":
        with pytest.raises(ValueError):
            read_page(path)
        assert not path.exists()
        return
    create_log(path)
    if mode == "corrupt":
        path.write_bytes(b"not a database")
    elif mode not in {"cancel", "identity"}:
        with sqlite3.connect(path) as db:
            if mode == "version":
                db.execute("PRAGMA user_version=999")
            if mode == "view":
                db.execute("ALTER TABLE samples RENAME TO old_samples")
                db.execute("CREATE VIEW samples AS SELECT * FROM old_samples")
            if mode == "json":
                db.execute("UPDATE samples SET raw_json='[]'")
            if mode == "oversized":
                db.execute("UPDATE samples SET raw_json=?", ("x" * 2_100_000,))
            if mode == "context":
                db.execute(
                    "UPDATE samples SET raw_json=?",
                    (json.dumps({"_hbkg_context": {"sequences": {"bad": []}}}),),
                )
    before = path.read_bytes()
    with pytest.raises(ValueError):
        read_sample(
            path,
            1,
            expected_session="other" if mode == "identity" else None,
            cancelled=lambda: mode == "cancel",
        )
    assert path.read_bytes() == before


def test_simulation_is_browsable_but_not_loaded_as_instrument(tmp_path):
    path = tmp_path / "demo.sqlite"
    create_log(path, origin="simulation")
    saved = read_sample(path, 1)
    assert saved.row.origin == "simulation" and saved.frame is None


def test_history_load_keeps_live_data_separate_and_waits_on_close(qtbot, tmp_path):
    path = tmp_path / "session.sqlite"
    _, sample = create_log(path)
    window = MainWindow(data_dir=tmp_path / "app")
    try:
        browser = window.history_browser
        browser.open_path(path)
        qtbot.waitUntil(lambda: browser.query is None)
        assert browser.table.rowCount() == 1
        browser.table.selectRow(0)
        browser.inspect_selected()
        qtbot.waitUntil(lambda: browser.query is None)
        assert browser.load.isEnabled()
        browser.load.click()
        page = window.frequency_page
        assert window.pages.currentIndex() == Page.FREQUENCY
        assert page.source.currentText() == "Saved session" and "sample 1" in page.notice.text()
        saved = page.frame
        window.receive_sample(sample)
        window.receive_status("stale", "fixture disconnected")
        assert page.frame is saved and page.frame.series[0].values == (-5, 0, None)
        assert window.table.rowCount() == 0 and not window.history
        page.source.setCurrentIndex(0)
        assert not page.frame.series
    finally:
        window.close()
        qtbot.waitUntil(lambda: window.thread_finished)


def test_cancel_late_history_result_and_shutdown(qtbot, tmp_path, monkeypatch):
    entered, release = threading.Event(), threading.Event()
    path = tmp_path / "session.sqlite"
    create_log(path)

    def slow(*args, **kwargs):
        entered.set()
        release.wait(3)
        return read_page(path)

    monkeypatch.setattr("bnkg.ui.history.read_page", slow)
    window = MainWindow(data_dir=tmp_path / "app")
    try:
        window.history_browser.open_path(path)
        qtbot.waitUntil(entered.is_set)
        window.close()
        assert not window.thread_finished
        release.set()
        qtbot.waitUntil(lambda: window.thread_finished)
        assert window.history_browser.page is None
    finally:
        release.set()
        window.close()
        qtbot.waitUntil(lambda: window.thread_finished)


def test_saved_cumulative_and_changed_bandwidth_use_each_rows_context(tmp_path):
    path = tmp_path / "basis.sqlite"
    store, sample = create_log(path, close=False)
    total = dict(
        DESC,
        Name="CPBLZeq",
        LocalName="LZeq",
        FunctionType="OctaveLeq",
        AveragingMode="Linear",
        PeriodTime=4294967296,
        DataAxisCpbNumberFractions=1,
    )
    store.append(
        replace(
            sample,
            raw_values={
                "CPBLZeq": [1000, 2000, 3000],
                "LZeq": 4500,
                "_hbkg_context": {
                    "sequences": {"CPBLZeq": total, "LZeq": dict(SCALAR, Name="LZeq")},
                    "setup_basis": {},
                },
            },
        )
    )
    store.close()
    first, second = read_sample(path, 1).frame, read_sample(path, 2).frame
    assert first.series[0].meaning.kind == "current"
    assert second.series[0].meaning.kind == "total"
    assert second.series[0].meaning.period_ms is None
    assert second.series[0].descriptor["DataAxisCpbNumberFractions"] == 1
    assert first.series[0].frequencies != second.series[0].frequencies
    assert dict(second.broadband)["LZeq"] == 45
    assert len(second.series) == 1  # No replacement A/C spectra.


def test_history_calculated_fields_and_failed_reread_clear_old_sample(qtbot, tmp_path):
    from bnkg.ui.history import HistoryBrowser

    path = tmp_path / "demo.sqlite"
    store = SessionStore(path, "simulation")
    store.append(DemoDevice().read())
    store.close()
    browser = HistoryBrowser(tmp_path)
    qtbot.addWidget(browser)
    browser.open_path(path)
    qtbot.waitUntil(lambda: browser.query is None)
    browser.table.selectRow(0)
    browser.inspect_selected()
    qtbot.waitUntil(lambda: browser.query is None)
    assert "Calculated fields" in browser.details.text()
    assert any(
        "Calculated" in browser.values.item(i, 0).text() for i in range(browser.values.rowCount())
    )
    with sqlite3.connect(path) as db:
        db.execute("UPDATE samples SET raw_json='bad'")
    browser.inspect_selected()
    qtbot.waitUntil(lambda: browser.query is None)
    assert browser.sample is None and not browser.load.isEnabled()
    assert "malformed" in browser.info.text()
