"""Build an Ubuntu x86-64 executable portable on Linux; no cross-compilation."""

import ast
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tarfile

from build_windows import ASSETS, ROOT, __version__, notices
from release_content import public_docs


def main():
    if sys.platform != "linux" or os.uname().machine != "x86_64":
        raise SystemExit("Build on Linux x86-64 (Ubuntu 22.04 baseline).")
    ASSETS.mkdir(exist_ok=True)
    stage = ROOT / "build" / "linux-notices"
    notices(stage)
    subprocess.run(
        [
            sys.executable,
            "-m",
            "PyInstaller",
            "--noconfirm",
            "--clean",
            "--onedir",
            "--name",
            "BnKG",
            "--additional-hooks-dir",
            str(ROOT / "packaging" / "hooks"),
            "--exclude-module",
            "PySide6.QtPdf",
            "--exclude-module",
            "PySide6.QtVirtualKeyboard",
            "--paths",
            str(ROOT / "src"),
            "--distpath",
            str(ROOT / "dist"),
            "--workpath",
            str(ROOT / "build" / "linux"),
            "--specpath",
            str(ROOT / "build"),
            "--add-data",
            f"{stage}:third-party-licenses",
            "--add-data",
            f"{ROOT / 'LICENSE'}:.",
            "--add-data",
            f"{ROOT / 'THIRD_PARTY_NOTICES.md'}:.",
            str(ROOT / "scripts" / "launch_app.py"),
        ],
        check=True,
        cwd=ROOT,
    )
    bundle = ROOT / "dist" / "BnKG"
    # Use Ubuntu's system libraries rather than redistributing runner-specific copies.
    # Keep Python/Qt/wheel libraries; their sources/notices are provided separately.
    analysis = ast.literal_eval((ROOT / "build" / "linux" / "BnKG" / "Analysis-00.toc").read_text())
    excluded = []

    def remove_system_rows(value):
        if isinstance(value, (list, tuple)):
            if len(value) == 3 and all(isinstance(item, str) for item in value):
                destination, source, kind = value
                if kind == "BINARY" and source.startswith(("/usr/lib/", "/lib/")):
                    target = (bundle / "_internal" / destination).absolute()
                    if not target.is_relative_to(bundle.absolute()):
                        raise RuntimeError("Unsafe binary destination")
                    target.unlink(missing_ok=True)
                    excluded.append(destination)
            else:
                for item in value:
                    remove_system_rows(item)

    remove_system_rows(analysis)
    for path in bundle.rglob("*"):
        if path.is_symlink() and not path.exists():
            path.unlink()
    (bundle / "system-libraries-not-bundled.json").write_text(
        json.dumps(sorted(excluded), indent=2)
    )
    public_docs(bundle)
    shutil.copy2(ROOT / "Launch-BnKG-Portable.sh", bundle)
    (bundle / "Launch-BnKG-Portable.sh").chmod(0o755)
    shutil.copytree(stage, bundle / "third-party-licenses", dirs_exist_ok=True)
    target = ASSETS / f"BnKG-{__version__}-linux-x86_64-Executable-Portable.tar.gz"
    with tarfile.open(target, "w:gz") as package:
        package.add(bundle, arcname="BnKG")
    with target.open("rb") as stream:
        digest = hashlib.file_digest(stream, "sha256").hexdigest()
    target.with_name(target.name + ".sha256").write_text(f"{digest}  {target.name}\n")
    print(target)


if __name__ == "__main__":
    main()
