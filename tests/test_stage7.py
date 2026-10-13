import json
import sqlite3
import threading
from dataclasses import replace

import pytest
from PySide6.QtWidgets import QMessageBox
from test_history import DESC, create_log

from bnkg.core.history import read_page
from bnkg.core.review import MAX_BYTES, add_marker, decode, encode, read_review, save_review
from bnkg.ui.history import HistoryBrowser
from bnkg.ui.window import MainWindow


def marker(path, ids=(1,), review=None, kind="M1"):
    return add_marker(
        path,
        review=review,
        ids=ids,
        kind=kind,
        note="<local> review",
        expected_session=dict(read_page(path).metadata)["session_id"],
    )


def test_review_roundtrip_relocation_append_and_immutable_raw(tmp_path):
    path = tmp_path / "source.sqlite"
    store, sample = create_log(path, 3, close=False)
    review = marker(path, (1, 2), kind="Exclude")
    store.append(sample)
    store.close()
    before = path.read_bytes()
    target = tmp_path / "review.bnkg-review.json"
    assert save_review(
        path, target=target, review=review, expected_session=review.session_id
    ) == str(target)
    assert path.read_bytes() == before
    renamed = tmp_path / "copied.sqlite"
    renamed.write_bytes(before)
    assert read_review(renamed, target=target, expected_session=review.session_id) == review
    payload = json.loads(target.read_bytes())
    assert "no acoustic quantities recalculated" in payload["basis"]
    assert "values" not in payload["markers"][0]["rows"][0]
    assert len(review.markers[0].rows) == 2  # Duplicate timestamps remain distinct IDs.
    with sqlite3.connect(renamed) as db:
        db.execute("UPDATE samples SET raw_json='{}' WHERE id=2")
    with pytest.raises(ValueError, match="sample 2 changed"):
        read_review(renamed, target=target, expected_session=review.session_id)
    other = tmp_path / "other.sqlite"
    create_log(other)
    with pytest.raises(ValueError, match="another session"):
        read_review(
            other, target=target, expected_session=dict(read_page(other).metadata)["session_id"]
        )
    assert path.read_bytes() == before


def test_review_publish_never_overwrites_and_cleans_cancelled_temp(tmp_path, monkeypatch):
    path = tmp_path / "source.sqlite"
    create_log(path)
    review = marker(path)
    target = tmp_path / "out.json"
    target.write_text("keep me")
    with pytest.raises(ValueError, match="existing files"):
        save_review(path, target=target, review=review, expected_session=review.session_id)
    assert target.read_text() == "keep me"
    target = tmp_path / "cancel.json"

    def abort(*args):
        raise ValueError("cancel at publication")

    monkeypatch.setattr("bnkg.core.review.guard", abort)
    # Empty review gets to the publication guard after the temporary write.
    with pytest.raises(ValueError, match="cancel at publication"):
        save_review(
            path,
            target=target,
            review=replace(review, markers=()),
            expected_session=review.session_id,
        )
    assert not target.exists() and not list(tmp_path.glob(".bnkg-review-*"))


@pytest.mark.parametrize("bad", ["size", "kind", "basis", "duplicate", "refs", "version"])
def test_review_rejects_malformed_or_unbounded_files(tmp_path, bad):
    path = tmp_path / "source.sqlite"
    create_log(path)
    review = marker(path)
    payload = json.loads(encode(review))
    if bad == "kind":
        payload["markers"][0]["kind"] = "Calculate exclusion"
    if bad == "basis":
        payload["basis"] = "certified interval"
    if bad == "duplicate":
        payload["markers"] *= 2
    if bad == "refs":
        payload["markers"][0]["rows"] *= 101
    if bad == "version":
        payload["version"] = True
    target = tmp_path / "bad.json"
    target.write_bytes(b" " * (MAX_BYTES + 1) if bad == "size" else json.dumps(payload).encode())
    with pytest.raises(ValueError):
        read_review(path, target=target, expected_session=review.session_id)
    assert not list(tmp_path.glob(".bnkg-review-*"))


def test_row_chart_spectrum_markers_and_page_jump(qtbot, tmp_path):
    path = tmp_path / "source.sqlite"
    store, sample = create_log(path, 101, close=False)
    total = dict(
        DESC,
        Name="CPBLZeq",
        LocalName="LZeq",
        FunctionType="OctaveLeq",
        AveragingMode="Linear",
        PeriodTime=4294967296,
    )
    store.append(
        replace(
            sample,
            raw_values={
                "CPBLZeq": [-500, 0, -32768],
                "_hbkg_context": {"sequences": {"CPBLZeq": total}, "setup_basis": {}},
            },
        )
    )
    store.close()
    before = path.read_bytes()
    browser = HistoryBrowser(tmp_path)
    qtbot.addWidget(browser)
    browser.open_path(path)
    qtbot.waitUntil(lambda: browser.query is None)
    browser.table.selectRow(1)
    qtbot.waitUntil(lambda: browser.sample is not None and browser.query is None)
    assert browser.sample.row.id == 2 and browser.chart.cursor_point.record_id == 2
    assert browser.saved_spectrum.sample.frame.series[0].values == (-5, 0, None)
    browser.review_panel.set_anchor()
    browser.chart.select_point(browser.chart.visible_points[3], emit=True)
    qtbot.waitUntil(
        lambda: browser.sample is not None and browser.sample.row.id == 4 and browser.query is None
    )
    assert browser.table.currentRow() == 3
    browser.review_panel.kind.setCurrentText("Exclude")
    browser.review_panel.add.click()
    qtbot.waitUntil(lambda: browser.query is None)
    review = browser.review_panel.review
    assert [r.id for r in review.markers[0].rows] == [2, 3, 4]
    assert browser.review_panel.dirty and browser.chart.markers == review.markers
    browser.turn_page(True)
    qtbot.waitUntil(lambda: browser.query is None)
    browser.table.selectRow(1)
    qtbot.waitUntil(lambda: browser.sample is not None and browser.query is None)
    assert browser.sample.row.id == 102
    assert browser.saved_spectrum.sample.frame.series[0].meaning.kind == "total"
    assert browser.saved_spectrum.sample.frame.series[0].meaning.period_ms is None
    browser.select_id(2)
    qtbot.waitUntil(
        lambda: browser.sample is not None and browser.sample.row.id == 2 and browser.query is None
    )
    assert browser.chart.cursor_point.record_id == 2
    target = tmp_path / "out.bnkg-review.json"
    browser.review_request("review_save", {"target": str(target), "review": review})
    qtbot.waitUntil(lambda: browser.query is None)
    assert not browser.review_panel.dirty and target.exists()
    assert decode(json.loads(target.read_bytes())) == review
    assert path.read_bytes() == before


def test_unsaved_guard_and_cancelled_late_marker_shutdown(qtbot, tmp_path, monkeypatch):
    path = tmp_path / "source.sqlite"
    create_log(path)
    window = MainWindow(data_dir=tmp_path / "app")
    entered, release = threading.Event(), threading.Event()
    try:
        browser = window.history_browser
        browser.open_path(path)
        qtbot.waitUntil(lambda: browser.query is None)
        browser.review_panel.completed("marker", marker(path))
        monkeypatch.setattr(QMessageBox, "question", lambda *args: QMessageBox.StandardButton.No)
        window.close()
        assert not window.closing and browser.review_panel.dirty
        browser.open_path(path)
        assert browser.review_panel.dirty
        browser.review_panel.dirty = False

        def slow(*args, **kwargs):
            entered.set()
            release.wait(3)
            return marker(path, kind="M2")

        monkeypatch.setattr("bnkg.ui.history.add_marker", slow)
        browser.review_request("marker", {})
        qtbot.waitUntil(entered.is_set)
        previous = browser.review_panel.review
        window.close()
        assert not window.thread_finished
        release.set()
        qtbot.waitUntil(lambda: window.thread_finished)
        assert browser.review_panel.review is previous
    finally:
        release.set()
        window.history_browser.review_panel.dirty = False
        window.close()
        qtbot.waitUntil(lambda: window.thread_finished)
