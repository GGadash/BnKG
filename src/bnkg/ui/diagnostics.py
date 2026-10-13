"""Connection evidence and an allowlisted local support summary; never probes."""

import json
import platform
from collections import deque
from datetime import UTC, datetime
from time import monotonic

from PySide6.QtCore import Qt, qVersion
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from bnkg import __version__

ACTIONS = {"StartPause", "Stop", "Identify", "KeyUp", "KeyDown", "KeyLeft", "KeyRight"}
MODES = {"instrument", "connecting", "disconnected", "stale", "simulation"}


def scalar(value):
    return (
        str(value)[:160] if isinstance(value, (str, int, float)) and value != "" else "Unavailable"
    )


class ConnectionDiagnostics(QWidget):
    def __init__(self):
        super().__init__()
        self.mode = "disconnected"
        self.identity = {}
        self.actions = []
        self.armed = False
        self.last_sample = None
        self.counts = {}
        self.events = deque(maxlen=32)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.summary = QLabel()
        self.summary.setWordWrap(True)
        self.summary.setTextFormat(Qt.TextFormat.PlainText)
        layout.addWidget(self.summary)
        self.table = QTableWidget(0, 2)
        self.table.setHorizontalHeaderLabels(["Connection evidence", "Last observed value"])
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.setColumnWidth(0, 150)
        self.table.setMaximumHeight(210)
        layout.addWidget(self.table)
        self.private = QCheckBox("Include private address and device identity in copied summary")
        layout.addWidget(self.private)
        buttons = QHBoxLayout()
        copy = QPushButton("Copy support summary")
        copy.clicked.connect(self.copy_summary)
        clear = QPushButton("Clear recent status history")
        clear.clicked.connect(self.events.clear)
        buttons.addWidget(copy)
        buttons.addWidget(clear)
        layout.addLayout(buttons)
        self.feedback = QLabel(
            "Summary is assembled locally. It excludes passwords, raw measurements, metadata values and local report notes. Review before sharing."
        )
        self.feedback.setWordWrap(True)
        layout.addWidget(self.feedback)
        self.refresh()

    def remember(self, address, identity):
        version = identity.get("Version", {})
        self.identity = {
            "Address": scalar(address),
            "Host": scalar(identity.get("HostName")),
            "Type": scalar(identity.get("Type")),
            "Device ID": scalar(identity.get("Id")),
            "Firmware": scalar(version.get("Firmware"))
            if isinstance(version, dict)
            else "Unavailable",
        }
        self.refresh()

    def set_mode(self, mode):
        mode = mode if mode in MODES else "unknown"
        if mode != self.mode:
            self.events.append({"pc_utc": datetime.now(UTC).isoformat(), "state": mode})
        self.mode = mode
        if mode == "connecting":
            self.identity = {}
        if mode != "instrument":
            self.last_sample = None
            self.counts = {}
            self.armed = False
        if mode in {"connecting", "disconnected", "simulation"}:
            self.actions = []
        self.refresh()

    def set_controls(self, armed, actions):
        self.armed = bool(armed)
        self.actions = sorted(ACTIONS.intersection(actions))
        self.refresh()

    def sample_seen(self, sample):
        if sample.origin != "instrument":
            return
        self.last_sample = monotonic()
        self.counts = {
            "scalar_fields": len(sample.values),
            "spectra": len(sample.spectra),
            "metadata_fields": len(sample.metadata),
        }
        self.refresh()

    def refresh(self):
        age = (
            f"last sample {max(0, monotonic() - self.last_sample):.0f} s ago"
            if self.last_sample is not None
            else "no fresh sample"
        )
        self.summary.setText(
            f"{self.mode.upper()} · {age}. Identity/access are last observed evidence, not a guarantee of every feature or licence. SLM controls {'armed' if self.armed else 'disarmed'}."
        )
        rows = [
            (
                "Identity basis",
                "Last verified connection"
                if self.mode == "instrument" and self.identity
                else "Retained / not live"
                if self.identity
                else "Not verified",
            )
        ]
        rows.extend(self.identity.items())
        rows.append(
            ("Advertised safe controls", ", ".join(self.actions) or "None currently available")
        )
        rows.append(
            (
                "Received fields",
                ", ".join(f"{key}: {value}" for key, value in self.counts.items()) or "Unavailable",
            )
        )
        self.table.setRowCount(len(rows))
        for row, values in enumerate(rows):
            for col, value in enumerate(values):
                item = QTableWidgetItem(str(value))
                item.setToolTip(str(value))
                self.table.setItem(row, col, item)

    def support_summary(self):
        result = {
            "application": "BnKG",
            "version": __version__,
            "python": platform.python_version(),
            "qt": qVersion(),
            "os": platform.system(),
            "connection_state": self.mode,
            "controls_armed": self.armed,
            "advertised_supported_controls": self.actions,
            "received_field_counts": dict(self.counts),
            "recent_states": list(self.events),
            "identity_scope": "included on request" if self.private.isChecked() else "omitted",
            "limitations": "No automatic probes; device support and recording/encoder acceptance depend on the actual hardware/build.",
        }
        if self.private.isChecked():
            result["last_identity"] = dict(self.identity)
        return json.dumps(result, indent=2)

    def copy_summary(self):
        QApplication.clipboard().setText(self.support_summary())
        self.feedback.setText(
            "Support summary copied locally"
            + (
                " with private identity; review before sharing."
                if self.private.isChecked()
                else " without device identity/address or measurement values."
            )
        )
