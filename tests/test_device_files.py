import threading
from datetime import date

import pytest
from PySide6.QtWidgets import QLabel, QTextBrowser

from bnkg import FULL_NAME
from bnkg.core.device_files import DATA, DeviceFilesClient
from bnkg.core.webxi import WebXiError
from bnkg.ui.about import AboutPage
from bnkg.ui.device_files import DeviceFilesPage
from bnkg.ui.window import MainWindow


def directory(**entries):
    return {"Metadata": {"Flags": "ReadOnly,Directory"}, **entries}


DIR = {"Metadata": {"Flags": "Directory"}}
FILE = {"Metadata": {"Flags": "ReadOnly,File"}}


def test_latest_date_filter_limit_and_advertised_paths(monkeypatch):
    client = DeviceFilesClient("127.0.0.1")
    calls = []
    trees = {
        DATA: directory(**{"2026_09_20": DIR, "2026_09_19": DIR, "Other": DIR}),
        DATA + "/2026_09_20": directory(**{"2026_09_20_02$01": DIR, "2026_09_20_01$00": DIR}),
        DATA + "/2026_09_19": directory(**{"2026_09_19_01": DIR}),
        DATA + "/2026_09_20/2026_09_20_02$01": directory(**{"result.total.bkc": FILE}),
    }

    def read(path, **kwargs):
        calls.append(path)
        return trees[path]

    monkeypatch.setattr(client, "_request_json", read)
    try:
        rows = client.latest(1)
        assert rows[0][0] == "2026_09_20_02$01"
        assert len(calls) == 2
        files = client.directory(rows[0][2])
        assert files[0][0] == "result.total.bkc" and files[0][1] == "File"
        assert client.latest(100, date(2026, 9, 19), date(2026, 9, 19))[0][0] == "2026_09_19_01"
        with pytest.raises(ValueError):
            client.directory(DATA + "/not-advertised")
        with pytest.raises(WebXiError, match="Cancelled"):
            client.latest(100, cancelled=lambda: True)
    finally:
        client.close()


@pytest.mark.parametrize("name", ["..", "../Setup", "x%2fSetup", "x?recursive", "x\\y", "x#y"])
def test_unsafe_names_refused(monkeypatch, name):
    client = DeviceFilesClient("127.0.0.1")
    monkeypatch.setattr(client, "_request_json", lambda *a, **k: directory(**{name: DIR}))
    try:
        with pytest.raises(WebXiError, match="Unsafe"):
            client.directory(DATA)
    finally:
        client.close()


def test_explicit_load_paging_dates_and_disconnect(qtbot, monkeypatch):
    page = DeviceFilesPage()
    qtbot.addWidget(page)
    calls = []
    monkeypatch.setattr(
        DeviceFilesClient,
        "latest",
        lambda self, *a, **k: (
            calls.append(a) or [(f"record-{i}", "Directory", DATA + f"/{i}") for i in range(205)]
        ),
    )
    assert page.limit.value() == 100 and not page.load.isEnabled()
    page.set_connection({"address": "127.0.0.1"})
    assert calls == []
    page.load_latest()
    qtbot.waitUntil(lambda: page.query is None)
    assert len(calls) == 1 and page.table.rowCount() == 100
    page.change_page(100)
    assert page.table.item(0, 0).text() == "record-100"
    page.change_page(100)
    assert page.table.rowCount() == 5
    page.dates.setChecked(True)
    page.start_date.setDate(page.end_date.date().addDays(1))
    page.load_latest()
    assert len(calls) == 1 and "Start date" in page.status.text()
    page.set_connection(None)
    assert not page.rows and page.table.rowCount() == 0 and not page.load.isEnabled()


def test_cancel_discards_late_results_and_window_waits(qtbot, tmp_path, monkeypatch):
    started = threading.Event()
    release = threading.Event()

    def slow(self, *a, **k):
        started.set()
        release.wait(3)
        return [("old record", "Directory", DATA + "/old")]

    monkeypatch.setattr(DeviceFilesClient, "latest", slow)
    window = MainWindow(data_dir=tmp_path)
    try:
        window.device_files.set_connection({"address": "127.0.0.1"})
        window.device_files.load_latest()
        qtbot.waitUntil(started.is_set)
        window.close()
        assert not window.thread_finished
        release.set()
        qtbot.waitUntil(lambda: window.thread_finished)
        assert window.device_files.rows == []
    finally:
        release.set()
        window.close()
        qtbot.waitUntil(lambda: window.thread_finished)


def test_about_name_credits_header_position(qtbot, tmp_path):
    about = AboutPage("Independent")
    qtbot.addWidget(about)
    text = " ".join(label.text() for label in about.findChildren(QLabel))
    text += about.findChild(QTextBrowser).toPlainText()
    for expected in (FULL_NAME, "B&KG = BnKG", "Sol 5.6", "Astra 6.0", "Tools used", "Discussions"):
        assert expected in text
    window = MainWindow(data_dir=tmp_path)
    try:
        window.show()
        assert window.windowTitle() == FULL_NAME
        assert any(label.text() == FULL_NAME for label in window.findChildren(QLabel))
        assert window.about_button.geometry().left() < window.theme.geometry().left()
        window.about_button.click()
        assert window.pages.currentIndex() == 7
        assert window.navigation.item(7).isHidden()
    finally:
        window.close()
        qtbot.waitUntil(lambda: window.thread_finished)
