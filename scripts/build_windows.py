"""Build curated Windows release assets. This script never tags or publishes."""

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import zipfile
from importlib.metadata import distributions
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from bnkg import __version__  # noqa: E402

ASSETS = ROOT / "release-assets"
from release_content import public_docs, public_source  # noqa: E402


def clean_environment():
    environment = dict(os.environ)
    windows = Path(os.environ["SystemRoot"])
    environment["PATH"] = os.pathsep.join(
        [str(Path(sys.executable).parent), sys.base_prefix, str(windows / "System32"), str(windows)]
    )
    for name in ("PYTHONPATH", "PYTHONHOME", "QT_PLUGIN_PATH", "QT_QPA_PLATFORM_PLUGIN_PATH"):
        environment.pop(name, None)
    return environment


def notices(target):
    target.mkdir(parents=True, exist_ok=True)
    shutil.copytree(
        ROOT / "packaging" / "licenses", target / "standard-licences", dirs_exist_ok=True
    )
    python_notice = ROOT / "packaging" / "licenses" / "Python-3.12-LICENSE.txt"
    if not python_notice.is_file():
        raise RuntimeError("Python runtime licence text is required.")
    shutil.copy2(python_notice, target / "Python-LICENSE.txt")
    inventory = []
    for distribution in distributions():
        name = distribution.metadata["Name"]
        inventory.append(
            {
                "name": name,
                "version": distribution.version,
                "license": distribution.metadata.get("License-Expression")
                or distribution.metadata.get("License", "See installed notices"),
            }
        )
        for file in distribution.files or ():
            parts = str(file).replace("\\", "/").split("/")
            if any(
                p.lower() in {"license", "licenses", "copying", "copyright", "notice"}
                or p.lower().startswith(("license.", "copying.", "notice."))
                for p in parts
            ):
                source = Path(distribution.locate_file(file))
                if source.is_file():
                    destination = target / name / Path(*[p for p in parts if p not in {"..", "."}])
                    destination.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(source, destination)
    (target / "build-environment-inventory.json").write_text(
        json.dumps(sorted(inventory, key=lambda i: i["name"].lower()), indent=2), encoding="utf-8"
    )
    shutil.copy2(ROOT / "docs" / "DEPENDENCY_SOURCES.md", target / "DEPENDENCY_SOURCES.md")
    source_info = ROOT / "packaging" / "source-provenance"
    if source_info.is_dir():
        shutil.copytree(source_info, target / "source-provenance", dirs_exist_ok=True)


def freeze(notice_dir, *, standalone=False):
    name = f"BnKG-{__version__}-win64-Standalone" if standalone else "BnKG"
    subprocess.run(
        [
            sys.executable,
            "-m",
            "PyInstaller",
            "--noconfirm",
            "--clean",
            "--windowed",
            "--onefile" if standalone else "--onedir",
            "--name",
            name,
            "--paths",
            str(ROOT / "src"),
            "--distpath",
            str(ASSETS if standalone else ROOT / "dist"),
            "--workpath",
            str(ROOT / "build" / ("standalone" if standalone else "portable")),
            "--specpath",
            str(ROOT / "packaging"),
            "--add-data",
            f"{notice_dir}{os.pathsep}third-party-licenses",
            "--add-data",
            f"{ROOT / 'LICENSE'}{os.pathsep}.",
            "--add-data",
            f"{ROOT / 'THIRD_PARTY_NOTICES.md'}{os.pathsep}.",
            str(ROOT / "scripts" / "launch_app.py"),
        ],
        cwd=ROOT,
        env=clean_environment(),
        check=True,
    )


def archive(directory, name):
    target = ASSETS / name
    with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as package:
        for path in sorted(directory.rglob("*")):
            if path.is_file() and "external-tools" not in path.relative_to(directory).parts:
                package.write(path, Path("BnKG") / path.relative_to(directory))
    with zipfile.ZipFile(target) as package:
        if package.testzip():
            raise RuntimeError("Archive CRC failed")
    return target


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--package-only",
        action="store_true",
        help="Refresh archives only; EXEs must already match the source version.",
    )
    args = parser.parse_args()
    if sys.platform != "win32":
        raise SystemExit("Build on Windows x64 with Python 3.12.")
    ASSETS.mkdir(exist_ok=True)
    stage = ROOT / "build" / "release-stage"
    if stage.exists():
        if not stage.resolve().is_relative_to((ROOT / "build").resolve()):
            raise RuntimeError("Unsafe stage path")
        shutil.rmtree(stage)
    stage.mkdir(parents=True, exist_ok=True)
    license_dir = stage / "third-party-licenses"
    notices(license_dir)
    if not args.package_only:
        freeze(license_dir)
        freeze(license_dir, standalone=True)
    bundle = ROOT / "dist" / "BnKG"
    executable = ASSETS / f"BnKG-{__version__}-win64-Standalone.exe"
    if not (bundle / "BnKG.exe").is_file() or not executable.is_file():
        raise RuntimeError("Both executable builds are required before packaging.")
    public_docs(bundle)
    shutil.copytree(license_dir, bundle / "third-party-licenses", dirs_exist_ok=True)
    (bundle / "Launch-BnKG-Portable.cmd").write_text(
        '@echo off\ncd /d "%~dp0"\n"%~dp0BnKG.exe" --data-dir "%~dp0data" %*\n', encoding="utf-8"
    )
    executable_zip = archive(bundle, f"BnKG-{__version__}-win64-Executable-Portable.zip")
    source = stage / "python"
    public_source(source)
    shutil.copytree(license_dir, source / "third-party-licenses", dirs_exist_ok=True)
    (source / "Launch-BnKG-Portable.cmd").write_text(
        '@echo off\ncd /d "%~dp0"\ncall "%~dp0Launch-BnKG.cmd" --data-dir "%~dp0data" %*\n',
        encoding="utf-8",
    )
    source_zip = archive(source, f"BnKG-{__version__}-Python-Portable.zip")
    shutil.copy2(ROOT / "Readme-info-which-relese-to-get.txt", ASSETS)
    license_zip = archive(license_dir, f"BnKG-{__version__}-Third-Party-Notices.zip")
    files = [
        executable,
        executable_zip,
        source_zip,
        license_zip,
        ASSETS / "Readme-info-which-relese-to-get.txt",
    ]
    checksums = []
    for path in files:
        with path.open("rb") as handle:
            digest = hashlib.file_digest(handle, "sha256").hexdigest()
        path.with_suffix(path.suffix + ".sha256").write_text(
            f"{digest}  {path.name}\n", encoding="utf-8"
        )
        checksums.append(f"{digest}  {path.name}")
    (ASSETS / "SHA256SUMS.txt").write_text("\n".join(checksums) + "\n", encoding="utf-8")
    print("Built release assets; verify packages before tagging or publishing.")
    for path in files:
        print(path)


if __name__ == "__main__":
    main()
