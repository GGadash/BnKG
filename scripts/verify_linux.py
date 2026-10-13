"""Check an extracted Linux release without an instrument or development imports."""

import argparse
import hashlib
import json
import os
import subprocess
import tarfile
import tempfile
from pathlib import Path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("archive", type=Path)
    args = parser.parse_args()
    archive = args.archive.resolve()
    with archive.open("rb") as stream:
        digest = hashlib.file_digest(stream, "sha256").hexdigest()
    assert archive.with_name(archive.name + ".sha256").read_text().split()[0] == digest
    with tempfile.TemporaryDirectory(prefix="BnKG Linux portable ") as directory:
        root = Path(directory)
        with tarfile.open(archive) as package:
            package.extractall(root, filter="data")
        env = {
            k: v
            for k, v in os.environ.items()
            if k
            not in {
                "PYTHONPATH",
                "PYTHONHOME",
                "QT_PLUGIN_PATH",
                "QT_QPA_PLATFORM_PLUGIN_PATH",
                "LD_LIBRARY_PATH",
            }
        }
        env["QT_QPA_PLATFORM"] = "xcb"
        data = root / "acceptance"
        subprocess.run(
            [str(root / "BnKG" / "BnKG"), "--smoke-test", "--data-dir", str(data)],
            env=env,
            cwd=root,
            check=True,
            timeout=60,
        )
        result = json.loads((data / "smoke-result.json").read_text())
        assert result["source"] == "disconnected" and result["logging"] is False
        print(
            json.dumps(
                {"sha256": digest, "state": result, "platform": os.uname().release}, indent=2
            )
        )


if __name__ == "__main__":
    main()
