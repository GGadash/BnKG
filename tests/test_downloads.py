import hashlib

import pytest

from bnkg.core.device_files import DATA, DeviceFilesClient
from bnkg.core.webxi import WebXiError


class Reply:
    def __init__(self, content=b"BKC fixture bytes", status=200, headers=None):
        self.content, self.status_code = content, status
        self.headers = {"Content-Length": str(len(content))} if headers is None else headers

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass

    def iter_content(self, chunk_size):
        for start in range(0, len(self.content), 3):
            yield self.content[start : start + 3]


class Session:
    def __init__(self, reply):
        self.reply, self.calls = reply, []

    def get(self, url, **options):
        self.calls.append((url, options))
        return self.reply

    def close(self):
        pass


def client(reply):
    session = Session(reply)
    instance = DeviceFilesClient("fixture.local", session)
    path = DATA + "/record$01/result.total.bkc"
    instance.files[path] = {"name": "result.total.bkc"}
    return instance, path, session


def test_original_download_hash_and_no_overwrite(tmp_path):
    data = b"\x00BKC-original\xff\x00"
    c, remote, session = client(Reply(data))
    path = tmp_path / "original.bkc"
    result = c.download(remote, path)
    assert path.read_bytes() == data and result["sha256"] == hashlib.sha256(data).hexdigest()
    assert result["bytes"] == len(data)
    assert "$" in session.calls[0][0] and "%24" not in session.calls[0][0]
    assert not session.calls[0][1]["allow_redirects"]
    with pytest.raises(FileExistsError):
        c.download(remote, path)
    assert len(session.calls) == 1 and path.read_bytes() == data
    assert list(tmp_path.glob("*.partial")) == []


@pytest.mark.parametrize(
    "failure",
    [
        "unadvertised",
        "redirect",
        "partial",
        "encoding",
        "length",
        "oversized",
        "stream_limit",
        "cancel",
        "race",
    ],
)
def test_download_rejects_incomplete_unsafe_and_cancelled_results(tmp_path, failure, monkeypatch):
    reply = Reply()
    if failure == "redirect":
        reply.status_code = 302
    if failure == "partial":
        reply.status_code = 206
    if failure == "encoding":
        reply.headers["Content-Encoding"] = "gzip"
    if failure == "length":
        reply.headers["Content-Length"] = "999"
    if failure == "oversized":
        reply.headers["Content-Length"] = str(300 * 1024 * 1024)
    if failure == "stream_limit":
        reply.headers = {}
    c, remote, session = client(reply)
    target = tmp_path / "result.bkc"
    calls = 0

    def cancel():
        nonlocal calls
        calls += 1
        return failure == "cancel" and calls > 1

    if failure == "race":
        import bnkg.core.device_files as module

        original = module.os.link

        def race(source, destination):
            target.write_bytes(b"existing")
            original(source, destination)

        monkeypatch.setattr(module.os, "link", race)
    with pytest.raises((ValueError, WebXiError, FileExistsError)):
        c.download(
            remote + "/../Setup" if failure == "unadvertised" else remote,
            target,
            max_bytes=4 if failure == "stream_limit" else 256 * 1024 * 1024,
            cancelled=cancel,
        )
    assert not target.exists() if failure != "race" else target.read_bytes() == b"existing"
    assert not list(tmp_path.glob("*.partial"))
    if failure == "unadvertised":
        assert not session.calls


def test_download_ui_uses_selected_advertised_file_off_thread(qtbot, tmp_path, monkeypatch):
    from bnkg.ui.device_files import DeviceFilesPage

    page = DeviceFilesPage()
    qtbot.addWidget(page)
    page.set_connection({"address": "fixture.local"})
    path = DATA + "/record$01/original.bkc"
    page.loaded(
        page.generation, [("original.bkc", "File", path)], {DATA}, {path: {"name": "original.bkc"}}
    )
    page.table.selectRow(0)
    assert page.download.isEnabled()
    target = tmp_path / "download.bkc"
    monkeypatch.setattr(
        "bnkg.ui.device_files.QFileDialog.getSaveFileName", lambda *args: (str(target), "")
    )

    def fake_download(self, source, destination, **options):
        assert source == path and source in self.files
        destination.write_bytes(b"original")
        return {
            "path": str(destination),
            "bytes": 8,
            "sha256": hashlib.sha256(b"original").hexdigest(),
        }

    monkeypatch.setattr(DeviceFilesClient, "download", fake_download)
    page.download.click()
    qtbot.waitUntil(lambda: page.query is None)
    assert target.read_bytes() == b"original"
    assert "SHA-256" in page.status.text()
