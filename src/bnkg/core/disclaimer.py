"""Versioned first-use terms shared by startup and About."""

import json
import os
import tempfile
from datetime import UTC, datetime
from pathlib import Path

from bnkg import __version__

AGREEMENT_REVISION = "2026-10-14"
DISCLAIMER = """B&KG is independent software by Gadash (Akila DJ), under development. Information may be incomplete, delayed or incorrect. It is not affiliated with, endorsed by or supported by Hottinger Brüel & Kjær. Manufacturer names and trademarks belong to their owners.

Use this software at your own risk. To the extent permitted by applicable law, the developer and distributors are not responsible for data loss, loss of measurements, or changes to SLM settings arising from its use. The software is provided without warranty, subject to its licence and applicable law.

Read and understand the instructions and each action before proceeding. Check the selected instrument, its current measurement state, settings and save status. Back up important data. Verify displayed values, units and settings on the physical instrument and against official documentation; do not rely only on the app's display or confirmations. This app does not establish calibration, measurement validity or regulatory compliance.

You may contact B&K/HBK to ask whether using third-party applications with your instrument, firmware, licences and intended workflow is appropriate. This suggestion does not imply manufacturer approval or support for B&KG.

Accepting this agreement does not arm controls or authorize any instrument action. Existing action confirmations and safety restrictions remain in effect."""


def agreement_accepted(directory: Path) -> bool:
    try:
        path = directory / "usage-agreement.json"
        if path.stat().st_size > 4096:
            return False
        record = json.loads(path.read_text(encoding="utf-8"))
        return (
            isinstance(record, dict)
            and record.get("accepted") is True
            and record.get("revision") == AGREEMENT_REVISION
        )
    except (OSError, ValueError, TypeError):
        return False


def save_acceptance(directory: Path) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    data = {
        "accepted": True,
        "revision": AGREEMENT_REVISION,
        "app_version": __version__,
        "accepted_utc": datetime.now(UTC).isoformat(),
    }
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=directory,
            prefix="agreement-",
            suffix=".tmp",
            delete=False,
        ) as stream:
            temporary = Path(stream.name)
            json.dump(data, stream, indent=2)
            stream.flush()
            os.fsync(stream.fileno())
        temporary.replace(directory / "usage-agreement.json")
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
