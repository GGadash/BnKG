"""Explicit public-source and package allowlists; never copy the workspace wholesale."""

import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PUBLIC_DOCS = (
    "README.md",
    "README-INFO.md",
    "QUICK_START.md",
    "RUN_PYTHON.md",
    "CONNECTION_GUIDE.md",
    "LICENSE",
    "LEGAL.md",
    "PRIVACY.md",
    "CREDITS.md",
    "THIRD_PARTY_NOTICES.md",
    "BUILDING.md",
    "CHANGELOG.md",
    "SECURITY.md",
    "CONTRIBUTING.md",
    "CONTENT_STRUCTURE.md",
    "Readme-info-which-relese-to-get.txt",
    "ARCHITECTURE.md",
    "ROADMAP.md",
)
PRIVATE_DOCS = {"SESSION_HISTORY.md", "HBKG_ADAPTATION_PLAN.md", "MOVING_PROJECT.md"}
PUBLIC_SCRIPTS = (
    "build_windows.py",
    "build_linux.py",
    "release_content.py",
    "prepare_public_source.py",
    "fetch_library_sources.py",
    "package_library_sources.py",
    "verify_portable.py",
    "verify_linux.py",
    "launch_app.py",
    "setup_after_move.py",
    "Setup-BnKG.ps1",
)
SOURCE_FILES = (
    "BnKG_Run_Python.py",
    "Launch-BnKG.cmd",
    "Launch-BnKG-Portable.sh",
    "Setup-BnKG-After-Move.cmd",
    "requirements.lock",
    "requirements-dev.lock",
    "pyproject.toml",
    "uv.lock",
    ".gitattributes",
    ".gitignore",
)


def copy_file(source, destination):
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, destination)


def public_docs(destination):
    destination = Path(destination)
    for name in PUBLIC_DOCS:
        copy_file(ROOT / name, destination / name)
    for path in (ROOT / "docs").glob("*.md"):
        if path.name not in PRIVATE_DOCS:
            copy_file(path, destination / "docs" / path.name)
    for directory in ("licenses", "screenshots", "wiki"):
        for path in (ROOT / "docs" / directory).rglob("*"):
            if path.is_file() and path.suffix.lower() in {".md", ".txt", ".png"}:
                copy_file(path, destination / path.relative_to(ROOT))


def public_source(destination):
    destination = Path(destination)
    public_docs(destination)
    for name in SOURCE_FILES:
        copy_file(ROOT / name, destination / name)
    for directory in (
        "src",
        "tests",
        "packaging/licenses",
        "packaging/hooks",
        "packaging/source-provenance",
        ".github/workflows",
    ):
        for path in (ROOT / directory).rglob("*"):
            if (
                path.is_file()
                and "__pycache__" not in path.parts
                and not path.name.endswith((".pyc", ".spec"))
            ):
                copy_file(path, destination / path.relative_to(ROOT))
    for name in PUBLIC_SCRIPTS:
        copy_file(ROOT / "scripts" / name, destination / "scripts" / name)
