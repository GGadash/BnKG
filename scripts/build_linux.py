"""Build an Ubuntu x86-64 executable portable on Linux; no cross-compilation."""

import hashlib
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
