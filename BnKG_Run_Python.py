"""Run BnKG from cmd, PowerShell or a Python file association.

Requires Python 3.12-3.14 and installed dependencies (see RUN_PYTHON.md).
Keep this file beside src/; it is the application launcher, not a single-file bundle.
"""

import os
import sys
from pathlib import Path


def main():
    root = Path(__file__).resolve().parent
    # A double-click with another installed Python may reuse the project's environment.
    local_python = root / ".venv" / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
    if local_python.exists() and Path(sys.prefix).resolve() != (root / ".venv").resolve():
        os.execv(
            str(local_python), [str(local_python), str(Path(__file__).resolve()), *sys.argv[1:]]
        )
    if not (3, 12) <= sys.version_info[:2] < (3, 15):
        raise RuntimeError(
            "BnKG requires Python 3.12, 3.13 or 3.14 (64-bit recommended). Read RUN_PYTHON.md."
        )
    sys.path.insert(0, str(root / "src"))
    try:
        from bnkg.app import main as run_app
    except ImportError as exc:
        raise RuntimeError(
            "BnKG dependencies are missing. Follow RUN_PYTHON.md to create .venv and install requirements.lock."
        ) from exc
    return run_app()


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as error:
        import traceback

        traceback.print_exc()
        if os.name == "nt":
            import ctypes

            ctypes.windll.user32.MessageBoxW(0, str(error), "BnKG startup", 0x10)
        raise SystemExit(1) from None
