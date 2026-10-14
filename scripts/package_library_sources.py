"""Package verified corresponding source archives beside binary release assets."""

import hashlib
import json
import sys
import tarfile
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from bnkg import __version__  # noqa: E402

if __name__ == "__main__":
    cache = ROOT / ".cache" / "release" / "dependency-sources"
    manifest = json.loads((cache / "SOURCE_MANIFEST.json").read_text())
    output = ROOT / "release-assets"
    output.mkdir(exist_ok=True)
    target = output / f"BnKG-{__version__}-Corresponding-Library-Sources.zip"
    with zipfile.ZipFile(target, "w", zipfile.ZIP_STORED) as package:
        for record in manifest:
            source = cache / record["file"]
            with source.open("rb") as stream:
                assert hashlib.file_digest(stream, "sha256").hexdigest() == record["sha256"]
            with tarfile.open(source) as archive:
                assert archive.getmembers()
            package.write(source, source.name)
        package.write(cache / "SOURCE_MANIFEST.json", "SOURCE_MANIFEST.json")
        package.write(ROOT / "docs" / "DEPENDENCY_SOURCES.md", "DEPENDENCY_SOURCES.md")
        for source in (ROOT / "packaging" / "source-provenance").glob("*"):
            if source.is_file():
                package.write(source, "build-provenance/" + source.name)
    with zipfile.ZipFile(target) as archive:
        assert archive.testzip() is None
    with target.open("rb") as stream:
        digest = hashlib.file_digest(stream, "sha256").hexdigest()
    target.with_suffix(".zip.sha256").write_text(f"{digest}  {target.name}\n")
    print(target.name, target.stat().st_size, "bytes; source hashes and archive CRC passed")
