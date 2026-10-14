"""Fetch unmodified source archives for redistributed copyleft libraries."""

import concurrent.futures
import hashlib
import json
import re
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / ".cache/release/dependency-sources"
OUT.mkdir(parents=True, exist_ok=True)
VERSION = "6.11.2"


def fetch(item):
    url, expected = item
    name = url.rsplit("/", 1)[-1]
    if "codeload.github.com/qt/" in url:
        name = "qt-build-instructions-6.11.2.tar.gz"
    if "codeload.github.com/FFmpeg/" in url:
        name = "FFmpeg-n7.1.5.tar.gz"
    p = OUT / name
    session = requests.Session()
    if "download.qt.io" in url:
        page = session.get(url + ".mirrorlist", timeout=40)
        page.raise_for_status()
        match = re.search(r"SHA-256 Hash.*?<tt>([a-f0-9]{64})</tt>", page.text, re.S)
        if not match:
            raise RuntimeError("No Qt source checksum: " + url)
        expected = match[1]
        links = re.findall(r'href="(https://[^\"]+\.tar\.xz)"', page.text)
        urls = [url] + [u for u in links if "jaist" in u or "ukfast" in u]
    else:
        urls = [url]
    if p.exists() and (not expected or hashlib.sha256(p.read_bytes()).hexdigest() == expected):
        pass
    else:
        last = None
        for download in urls:
            try:
                with session.get(download, stream=True, timeout=(20, 60)) as reply:
                    reply.raise_for_status()
                    with p.with_suffix(p.suffix + ".partial").open("wb") as output:
                        for block in reply.iter_content(1024 * 1024):
                            output.write(block)
                digest = hashlib.sha256(
                    p.with_suffix(p.suffix + ".partial").read_bytes()
                ).hexdigest()
                if expected and digest != expected:
                    raise RuntimeError("Checksum mismatch " + name)
                p.with_suffix(p.suffix + ".partial").replace(p)
                break
            except Exception as e:
                last = e
        else:
            raise last
    if (
        name == "FFmpeg-n7.1.5.tar.gz"
        and hashlib.sha1(p.read_bytes()).hexdigest() != "2322a4cef2d607c7f0048953662ec5e27c587ae8"
    ):
        raise RuntimeError("FFmpeg source differs from Qt provisioning checksum")
    result = {
        "file": name,
        "url": url,
        "sha256": hashlib.sha256(p.read_bytes()).hexdigest(),
        "upstream_sha256": expected,
        "bytes": p.stat().st_size,
    }
    print("Source ready:", name, flush=True)
    return result


if __name__ == "__main__":
    qt = "https://download.qt.io/archive/qt/6.11/6.11.2/submodules/"
    items = [
        (qt + m + "-everywhere-src-6.11.2.tar.xz", None)
        for m in [
            "qtbase",
            "qtsvg",
            "qtmultimedia",
            "qtdeclarative",
            "qtshadertools",
            "qtimageformats",
            "qtwayland",
            "qttranslations",
            "qttools",
        ]
    ]
    items += [
        (
            "https://download.qt.io/official_releases/QtForPython/pyside6/PySide6-6.11.2-src/pyside-setup-everywhere-src-6.11.2.tar.xz",
            None,
        ),
        ("https://ffmpeg.org/releases/ffmpeg-7.1.5.tar.xz", None),
        ("https://codeload.github.com/FFmpeg/FFmpeg/tar.gz/refs/tags/n7.1.5", None),
        ("https://zlib.net/fossils/zlib-1.3.1.tar.gz", None),
        ("https://codeload.github.com/qt/qt5/tar.gz/refs/tags/v6.11.2", None),
    ]
    for package, version in [("zeroconf", "0.151.3")]:
        r = requests.get(f"https://pypi.org/pypi/{package}/{version}/json", timeout=30)
        r.raise_for_status()
        source = next(f for f in r.json()["urls"] if f["packagetype"] == "sdist")
        items.append((source["url"], source["digests"]["sha256"]))
    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
        records = list(pool.map(fetch, items))
    (OUT / "SOURCE_MANIFEST.json").write_text(json.dumps(records, indent=2), encoding="utf-8")
    print("All source archives downloaded and hashed.", flush=True)
