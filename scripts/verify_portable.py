"""Verify a portable Windows ZIP independently of the development environment."""

import argparse
import hashlib
import json
import os
import subprocess
import tempfile
import time
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("archive", type=Path)
    parser.add_argument("--results", type=Path, default=ROOT / "artifacts" / "portable-validation")
    args = parser.parse_args()
    archive = args.archive.resolve()
    with archive.open("rb") as handle:
        digest = hashlib.file_digest(handle, "sha256").hexdigest()
    checksum_file = archive.with_suffix(".zip.sha256")
    if checksum_file.read_text(encoding="utf-8").split()[0] != digest:
        raise RuntimeError("Portable archive SHA-256 does not match its sidecar.")
    cache = ROOT / ".cache"
    cache.mkdir(exist_ok=True)
    destination = Path(tempfile.mkdtemp(prefix="BnKG portable ", dir=cache))
    with zipfile.ZipFile(archive) as package:
        if package.testzip():
            raise RuntimeError("Portable archive CRC verification failed.")
        for entry in package.infolist():
            resolved = (destination / entry.filename).resolve()
            if not resolved.is_relative_to(destination.resolve()):
                raise RuntimeError("Unsafe archive path.")
        file_count = len(package.infolist())
        package.extractall(destination)
    executable = destination / "BnKG" / "BnKG.exe"
    environment = dict(os.environ, QT_QPA_PLATFORM="windows")
    windows = Path(os.environ["SystemRoot"])
    environment["PATH"] = os.pathsep.join([str(windows / "System32"), str(windows)])
    for name in ("PYTHONHOME", "PYTHONPATH", "QT_PLUGIN_PATH", "QT_QPA_PLATFORM_PLUGIN_PATH"):
        environment.pop(name, None)
    data = destination / "acceptance-data"
    args.results.mkdir(parents=True, exist_ok=True)
    screenshot = (args.results / "dashboard-frozen.png").resolve()
    started = time.monotonic()
    process = subprocess.run(
        [str(executable), "--smoke-test", "--data-dir", str(data), "--screenshot", str(screenshot)],
        cwd=destination,
        env=environment,
        capture_output=True,
        timeout=45,
        creationflags=subprocess.CREATE_NO_WINDOW,
    )
    (args.results / "startup.log").write_bytes(process.stdout + process.stderr)
    if process.returncode:
        raise RuntimeError(f"Frozen app exited with {process.returncode}; inspect startup.log.")
    state = json.loads((data / "smoke-result.json").read_text(encoding="utf-8"))
    if (
        state["source"] != "disconnected"
        or state.get("logging") is not False
        or not screenshot.is_file()
    ):
        raise RuntimeError("Frozen app did not complete its disconnected smoke test.")
    report = {
        "status": "passed",
        "archive": archive.name,
        "sha256": digest,
        "archive_entries": file_count,
        "elapsed_seconds": round(time.monotonic() - started, 2),
        "test": "Extracted copy in a path containing spaces; Windows-only PATH; native Qt rendering",
        "app_state": state,
        "extracted_test_copy": str(destination),
        "limitation": "Same Windows PC, not a clean second-computer acceptance test.",
    }
    (args.results / "verification.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
