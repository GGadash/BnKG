"""BnKG entrypoint. Starts disconnected unless --demo is explicitly requested."""

import argparse
import shutil
import sys
from pathlib import Path

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication

from bnkg import __version__
from bnkg.ui.window import MainWindow


def main() -> int:
    parser = argparse.ArgumentParser(description="BnKG desktop studio")
    parser.add_argument(
        "--demo", action="store_true", help="Start with clearly labelled synthetic data"
    )
    parser.add_argument(
        "--data-dir", type=Path, help="Override local sessions/preferences directory"
    )
    parser.add_argument(
        "--smoke-test",
        action="store_true",
        help="Exercise startup and clean shutdown without hardware",
    )
    parser.add_argument("--screenshot", type=Path, help="Save a UI capture during smoke testing")
    parser.add_argument("--version", action="version", version=__version__)
    parser.add_argument(
        "--extract-notices",
        type=Path,
        help="Copy bundled licence notices into a new directory and exit",
    )
    args = parser.parse_args()
    if args.extract_notices:
        base = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parents[2]))
        source = base / "third-party-licenses"
        if not source.is_dir():
            parser.error(
                "Bundled notices are not present; see THIRD_PARTY_NOTICES.md in the source edition."
            )
        if args.extract_notices.exists():
            parser.error(
                "Choose a new directory for extracted notices; existing files are not overwritten."
            )
        shutil.copytree(source, args.extract_notices)
        for name in ("LICENSE", "THIRD_PARTY_NOTICES.md"):
            if (base / name).is_file():
                shutil.copy2(base / name, args.extract_notices / name)
        return 0
    app = QApplication(sys.argv[:1])
    app.setOrganizationName("Gadash")
    app.setApplicationName("BnKG")
    app.setApplicationVersion(__version__)
    app.setStyle("Fusion")
    window = MainWindow(data_dir=args.data_dir, demo=args.demo or args.smoke_test)
    window.show()
    if args.smoke_test:

        def finish() -> None:
            if args.screenshot:
                args.screenshot.parent.mkdir(parents=True, exist_ok=True)
                if not window.grab().save(str(args.screenshot), "PNG"):
                    raise RuntimeError("Smoke-test screenshot failed.")
            if args.data_dir:
                args.data_dir.mkdir(parents=True, exist_ok=True)
                (args.data_dir / "smoke-result.json").write_text(
                    window.diagnostic_snapshot(), encoding="utf-8"
                )
            window.close()

        QTimer.singleShot(2500, finish)
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
