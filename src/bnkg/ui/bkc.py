"""Local BKC inspection and validated stored totals; no network or weighting synthesis."""

import json

from PySide6.QtCore import QThread, Signal
from PySide6.QtWidgets import (
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QPlainTextEdit,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from bnkg.core.bkc import decode_total, read_bkc, save_raw_report


class BkcJob(QThread):
    result = Signal(object)
    failed = Signal(str)

    def __init__(self, path, report=None):
        super().__init__()
        self.path = path
        self.report = report

    def run(self):
        try:
            if self.report is not None:
                if not self.isInterruptionRequested():
                    save_raw_report(self.report, self.path)
                    self.result.emit({"saved": str(self.path)})
                return
            result = read_bkc(self.path, cancelled=self.isInterruptionRequested)
            result["_decoded"] = decode_total(result)
            if not self.isInterruptionRequested():
                self.result.emit(result)
        except Exception as exc:
            if not self.isInterruptionRequested():
                self.failed.emit(str(exc))


class BkcPanel(QWidget):
    spectrum_selected = Signal(object, str)
    idle = Signal()

    def __init__(self, folder):
        super().__init__()
        self.folder = folder
        self.job = None
        self.result = None
        self.decoded = None
        layout = QVBoxLayout(self)
        note = QLabel(
            "NATIVE BKC — stored measurement totals. Validated 2255 profiles show instrument values in dB; unsupported profiles remain raw-only. A/Z spectra are read directly, never synthesized. Originals stay unchanged; signature authenticity is not verified."
        )
        note.setWordWrap(True)
        layout.addWidget(note)
        row = QHBoxLayout()
        self.open = QPushButton("Open BKC…")
        self.save = QPushButton("Save raw inspection JSON…")
        self.cancel = QPushButton("Cancel")
        self.load = QPushButton("Load saved A/Z spectra in Frequency")
        self.load.setEnabled(False)
        self.load.clicked.connect(self.load_spectrum)
        self.open.clicked.connect(self.choose)
        self.save.clicked.connect(self.export)
        self.cancel.clicked.connect(self.stop)
        for item in (self.open, self.save, self.cancel, self.load):
            row.addWidget(item)
        layout.addLayout(row)
        self.status = QLabel(
            "Supported: observed version-0 container, Storage 2, single-record Int16/Double table. Other layouts are rejected."
        )
        self.status.setWordWrap(True)
        layout.addWidget(self.status)
        self.table = QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels(
            ["ID", "Name", "Function", "Weighting", "Raw values (not dB)"]
        )
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.itemSelectionChanged.connect(self.details)
        layout.addWidget(self.table)
        self.detail = QPlainTextEdit()
        self.detail.setReadOnly(True)
        self.detail.setMaximumHeight(180)
        layout.addWidget(self.detail)
        self.save.setEnabled(False)
        self.cancel.setEnabled(False)

    def choose(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Open native BKC", str(self.folder), "BKC (*.bkc)"
        )
        if path:
            self.open_path(path)

    def open_path(self, path):
        if self.job:
            return
        self.result = None
        self.table.setRowCount(0)
        self.detail.clear()
        self.save.setEnabled(False)
        self.load.setEnabled(False)
        self.decoded = None
        self.open.setEnabled(False)
        self.cancel.setEnabled(True)
        self.job = BkcJob(path)
        self.job.result.connect(self.receive)
        self.job.failed.connect(self.status.setText)
        self.job.finished.connect(self.finished)
        self.job.start()

    def receive(self, result):
        if self.job.isInterruptionRequested():
            return
        if "saved" in result:
            self.status.setText("Saved native inspection and decoded totals: " + result["saved"])
            return
        self.decoded = result.pop("_decoded", None)
        self.result = result
        self.status.setText(
            f"{result['file']} · {len(result['raw_rows'])} raw sequences · {result['status']} · {len(result['checked_part_hashes'])} part hashes match; signature authenticity unverified"
        )
        if self.decoded:
            self.status.setText(
                f"{result['file']} · stored measurement total · {self.decoded['elapsed_s']:g} s elapsed · validated 2255 decoding profile · direct A/Z; no C synthesis. Quality/authenticity limitations remain in details."
            )
        self.load.setEnabled(bool(self.decoded and self.decoded["frame"].series))
        self.table.setHorizontalHeaderLabels(
            ["ID", "Name", "Function", "Weighting", "Stored dB / raw where unsupported"]
        )
        self.table.setRowCount(len(result["raw_rows"]))
        for i, row in enumerate(result["raw_rows"]):
            for j, value in enumerate(
                [
                    row["sequence_id"],
                    row["name"],
                    row["function"],
                    row["weighting"],
                    self.display_values(row),
                ]
            ):
                self.table.setItem(i, j, QTableWidgetItem(str(value or "")))
        self.table.resizeColumnsToContents()
        self.save.setEnabled(True)

    def display_values(self, row):
        decoded = (
            next((v for v in self.decoded["rows"] if v["name"] == row["name"]), None)
            if self.decoded
            else None
        )
        return (str(decoded["values"]) + " dB") if decoded else (str(row["raw_values"]) + " (raw)")

    def load_spectrum(self):
        if self.decoded:
            self.spectrum_selected.emit(
                self.decoded["frame"], self.result["file"] + " · BKC measurement total"
            )

    def details(self):
        i = self.table.currentRow()
        if self.result and 0 <= i < len(self.result["raw_rows"]):
            detail = self.result["raw_rows"][i]["descriptor_xml"]
            if self.decoded:
                detail += "\n\n" + json.dumps(self.decoded["provenance"], indent=2)
            self.detail.setPlainText(detail)

    def export(self):
        if not self.result or self.job:
            return
        path, _ = QFileDialog.getSaveFileName(
            self,
            "Save private raw inspection",
            str(self.folder / "bkc-inspection.json"),
            "JSON (*.json)",
        )
        if path:
            report = dict(self.result)
            if self.decoded:
                report["decoded_total"] = {
                    "rows": self.decoded["rows"],
                    "provenance": self.decoded["provenance"],
                }
            self.save.setEnabled(False)
            self.open.setEnabled(False)
            self.cancel.setEnabled(True)
            self.job = BkcJob(path, report)
            self.job.result.connect(self.receive)
            self.job.failed.connect(self.status.setText)
            self.job.finished.connect(self.finished)
            self.job.start()

    def stop(self):
        if self.job:
            self.job.requestInterruption()

    def finished(self):
        self.job.deleteLater()
        self.job = None
        self.open.setEnabled(True)
        self.save.setEnabled(self.result is not None)
        self.cancel.setEnabled(False)
        self.idle.emit()
