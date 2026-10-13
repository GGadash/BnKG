"""Instrument-only frequency and metadata views, and an isolated demo workspace."""

import csv
import math
from collections import deque
from dataclasses import replace
from datetime import datetime
from html import escape

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFileDialog,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from bnkg.core.device import DEMO_MODES, DemoDevice
from bnkg.core.measurements import metadata_text
from bnkg.core.parameters import BY_ID
from bnkg.core.report_context import metadata_group
from bnkg.ui.frequency import FrequencyPage
from bnkg.ui.location import LocationPanel
from bnkg.ui.presentation import ParameterTile
from bnkg.ui.report_context import ReportContextPanel


def label(text):
    widget = QLabel(text)
    widget.setWordWrap(True)
    return widget


def readonly_table(headers):
    table = QTableWidget(0, len(headers))
    table.setHorizontalHeaderLabels(headers)
    table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
    table.horizontalHeader().setStretchLastSection(True)
    return table


class MetadataPage(QWidget):
    selected_changed = Signal(str)

    def __init__(self, settings):
        super().__init__()
        self.settings = settings
        self.selected = set(
            settings.value("metadata_visible", ["SerialNumber", "Latitude", "Longitude"])
        )
        self.fields = {}
        layout = QVBoxLayout(self)
        layout.addWidget(
            label(
                "METADATA · Select fields to show on the dashboard. Values and access flags come from the connected SLM."
            )
        )
        layout.addWidget(
            label(
                "HBK 2255 has integrated GPS. Unavailable coordinates mean no usable location, not missing hardware. GPS outputs are read-only; external coordinate injection is not verified. Configure the nine metadata slots (for example Location or Operator) on the physical SLM. Disabled slots may advertise read-only fields. No verified project-name/save-filename setter is implemented."
            )
        )
        self.tabs = QTabWidget()
        layout.addWidget(self.tabs)
        instrument = QWidget()
        instrument_layout = QVBoxLayout(instrument)
        self.search = QLineEdit()
        self.search.setPlaceholderText("Find instrument metadata by field or value…")
        self.search.setAccessibleName("Search instrument metadata")
        self.group = QComboBox()
        self.group.addItems(
            [
                "All groups",
                "Identity",
                "Location",
                "SLM metadata slots",
                "Battery and storage",
                "Transducer and calibration",
                "Weather",
                "Measurement and setup",
            ]
        )
        instrument_layout.addWidget(self.search)
        instrument_layout.addWidget(self.group)
        self.field_count = label("No instrument metadata received.")
        instrument_layout.addWidget(self.field_count)
        self.search.textChanged.connect(self.filter_fields)
        self.group.currentTextChanged.connect(self.filter_fields)
        self.location = LocationPanel()
        self.report = ReportContextPanel(settings)
        self.tabs.addTab(instrument, "Instrument fields")
        self.tabs.addTab(self.location, "Location / transfer")
        self.tabs.addTab(self.report, "Local report")
        self.table = readonly_table(["Show", "Field", "Value / raw format", "Device access"])
        self.table.setMinimumHeight(220)
        self.table.itemChanged.connect(self.changed)
        instrument_layout.addWidget(self.table)
        self.table.setColumnWidth(0, 50)
        self.table.setColumnWidth(1, 210)
        self.table.setColumnWidth(2, 200)

    def update_fields(self, fields):
        self.fields = fields
        self.table.blockSignals(True)
        self.table.setRowCount(len(fields))
        for row, (key, field) in enumerate(sorted(fields.items())):
            check = QTableWidgetItem()
            check.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsUserCheckable)
            check.setCheckState(
                Qt.CheckState.Checked if key in self.selected else Qt.CheckState.Unchecked
            )
            check.setData(Qt.ItemDataRole.UserRole, key)
            self.table.setItem(row, 0, check)
            for col, text in enumerate(
                (
                    key,
                    metadata_text(field),
                    field.get("access", "Unknown; no writes allowed"),
                ),
                1,
            ):
                item = QTableWidgetItem(text)
                item.setToolTip(
                    field.get("description", "") + "\nDomain: " + str(field.get("domain", ""))
                )
                self.table.setItem(row, col, item)
        self.table.blockSignals(False)
        self.filter_fields()
        self.publish()

    def filter_fields(self, *_):
        search = self.search.text().strip().casefold()
        group = self.group.currentText()
        visible = 0
        for row in range(self.table.rowCount()):
            key = self.table.item(row, 0).data(Qt.ItemDataRole.UserRole)
            match = (group == "All groups" or metadata_group(key) == group) and (
                not search or search in (key + " " + metadata_text(self.fields[key])).casefold()
            )
            self.table.setRowHidden(row, not match)
            visible += int(match)
        self.field_count.setText(
            f"{visible} of {len(self.fields)} received fields · Display filters do not change acquisition, selected dashboard fields or device access."
        )

    def changed(self, item):
        if item.column() != 0:
            return
        key = item.data(Qt.ItemDataRole.UserRole)
        if item.checkState() == Qt.CheckState.Checked:
            self.selected.add(key)
        else:
            self.selected.discard(key)
        self.settings.setValue("metadata_visible", sorted(self.selected))
        self.publish()

    def publish(self):
        parts = []
        for key in sorted(self.selected):
            field = self.fields.get(key)
            if field:
                parts.append(f"{escape(key)}: {escape(metadata_text(field))}")
        self.selected_changed.emit(
            "SLM metadata · " + " · ".join(parts)
            if parts
            else "Select fields in Metadata to show them here."
        )


class DemoPage(QWidget):
    """A separate simulator; it never touches the instrument worker or its logs."""

    def __init__(self, settings=None):
        super().__init__()
        self.device = None
        self.latest = None
        self.rows = deque(maxlen=100)
        self.save_handle = None
        self.writer = None
        layout = QVBoxLayout(self)
        layout.addWidget(
            label(
                "DEMO LAB · SYNTHETIC DATA ONLY\nIndependent preview. Main instrument tabs remain unchanged. CSV saves main values only."
            )
        )
        row = QHBoxLayout()
        self.mode = QComboBox()
        self.mode.addItems(DEMO_MODES)
        self.start = QPushButton("Start demo")
        self.start.clicked.connect(self.toggle)
        self.pause = QPushButton("Pause")
        self.pause.setEnabled(False)
        self.pause.clicked.connect(self.toggle_pause)
        for w in (self.mode, self.start, self.pause):
            row.addWidget(w)
        layout.addLayout(row)
        options = QHBoxLayout()
        self.seed = QSpinBox()
        self.seed.setRange(0, 999999)
        self.seed.setValue(7)
        self.seed.setPrefix("Seed: ")
        self.seed.setToolTip("Use the same seed and scenario for repeatable simulated readings.")
        options.addWidget(self.seed)
        self.event = QPushButton("Inject demo event")
        self.event.setEnabled(False)
        self.event.clicked.connect(lambda: self.device.inject_event() if self.device else None)
        options.addWidget(self.event)
        layout.addLayout(options)
        self.capture = QCheckBox("Capture demo table (newest 100)")
        layout.addWidget(self.capture)
        self.save = QPushButton("Start simple CSV logging…")
        self.save.clicked.connect(self.toggle_save)
        layout.addWidget(self.save)
        self.readings = label("Start a scenario to preview readings.")
        layout.addWidget(self.readings)
        self.tabs = QTabWidget()
        overview = QWidget()
        overview_layout = QVBoxLayout(overview)
        overview_layout.setContentsMargins(0, 0, 0, 0)
        self.tiles = {}
        tiles_layout = QGridLayout()
        for i, key in enumerate(("LAF", "LAeq", "LCeq", "LCpeak")):
            tile = ParameterTile(key, BY_ID[key].description)
            tile.caption.setText(key + " · Synthetic")
            self.tiles[key] = tile
            tiles_layout.addWidget(tile, i // 2, i % 2)
        overview_layout.addLayout(tiles_layout)
        self.frequency = FrequencyPage(settings, demo=True)
        self.frequency.heading.setText("DEMO SPECTRUM · illustrative synthetic 1/3-octave preview")
        self.tabs.addTab(overview, "Readings & data")
        self.tabs.addTab(self.frequency, "Frequency")
        self.table = readonly_table(["PC UTC", "LAF dB", "LAeq dB", "LCpeak dB"])
        overview_layout.addWidget(self.table, 1)
        layout.addWidget(self.tabs, 1)
        self.timer = QTimer(self)
        self.timer.setInterval(1000)
        self.timer.timeout.connect(self.poll)

    def toggle(self):
        if self.device:
            self.stop()
            return
        self.device = DemoDevice(self.mode.currentText(), seed=self.seed.value())
        self.seed.setEnabled(False)
        self.event.setEnabled(True)
        self.start.setText("Stop demo")
        self.pause.setEnabled(True)
        self.mode.setEnabled(False)
        self.pause.setText("Pause")
        self.timer.start()
        self.poll()

    def toggle_pause(self):
        if self.device:
            self.device.toggle()
            self.pause.setText("Pause" if self.device.running else "Resume")
            self.event.setEnabled(self.device.running)
            self.frequency.live_frame = replace(
                self.frequency.live_frame,
                state="Demo running"
                if self.device.running
                else "Demo paused; last sample retained",
            )
            if self.frequency.source.currentIndex() == 0:
                self.frequency.select_frame()
            if not self.device.running:
                self.readings.setText("SYNTHETIC · Paused; last simulated readings retained")

    def poll(self):
        if not self.device or not self.device.running:
            return
        sample = self.latest = self.device.read()
        self.readings.setText(
            f"SYNTHETIC · {self.mode.currentText()} · seed {self.seed.value()} · step {sample.elapsed_s:.0f}. Illustrative values, not an acoustic model."
        )
        for key, tile in self.tiles.items():
            value = sample.values.get(key)
            tile.value.setText("N/A" if value is None else f"{value:.1f}")
        spectra = {}
        # Independently scripted illustrations, not A/C weighting conversions from Z.
        for weight, offset, phase in (("Z", 5, 0), ("C", 2, 0.6), ("A", 0, 1.2)):
            quantity = "L" + weight + "F"
            spectra["CPB" + quantity] = {
                "frequencies": [10 ** (0.1 * i) for i in range(11, 44)],
                "values": [
                    sample.values["LAF"]
                    - 10
                    + offset
                    + 8 * math.sin(i / 4 + sample.elapsed_s / 9 + phase)
                    for i in range(33)
                ],
                "descriptor": {
                    "LocalName": quantity,
                    "AcousticalWeighting": weight,
                    "FunctionType": "OctaveL",
                    "AveragingMode": "Fast",
                    "Unit": "dB re 20uPa",
                    "DataAxisCpbNumberFractions": 3,
                },
                "origin": "simulation",
            }
        self.frequency.update_spectra(
            spectra,
            broadband=sample.values,
            timestamp=sample.timestamp.isoformat(),
            state=sample.state,
            quality="Synthetic scripted bands; not an acoustic calculation or a 125 ms Leq stream. Demo refresh: 1 s.",
        )
        record = [
            sample.timestamp.isoformat(),
            *(f"{sample.values[k]:.2f}" for k in ("LAF", "LAeq", "LCpeak")),
        ]
        if self.capture.isChecked() or self.writer:
            self.rows.append(record)
            self.table.setRowCount(len(self.rows))
            for row, values in enumerate(self.rows):
                for col, value in enumerate(values):
                    self.table.setItem(row, col, QTableWidgetItem(value))
        if self.writer:
            try:
                self.writer.writerow(record)
                self.save_handle.flush()
            except OSError as exc:
                self.stop_save()
                QMessageBox.warning(self, "Demo CSV", str(exc))

    def toggle_save(self):
        if self.writer:
            self.stop_save()
            return
        if not self.device:
            QMessageBox.information(self, "Demo CSV", "Start demo first.")
            return
        path, _ = QFileDialog.getSaveFileName(
            self,
            "New synthetic demo CSV",
            f"BnKG-Demo-{datetime.now():%Y%m%d-%H%M%S}.csv",
            "CSV (*.csv)",
        )
        if path:
            try:
                self.save_handle = open(path, "x", newline="", encoding="utf-8")
                self.writer = csv.writer(self.save_handle)
                self.writer.writerow(["PC_UTC_SYNTHETIC", "LAF_dB", "LAeq_dB", "LCpeak_dB"])
                self.save.setText("Stop demo CSV logging")
            except OSError as exc:
                self.stop_save()
                QMessageBox.warning(self, "Demo CSV", str(exc))

    def stop_save(self):
        if self.save_handle:
            self.save_handle.close()
        self.save_handle = self.writer = None
        self.save.setText("Start simple CSV logging…")

    def stop(self):
        self.timer.stop()
        self.stop_save()
        if self.device:
            self.device.close()
        self.device = None
        self.start.setText("Start demo")
        self.pause.setEnabled(False)
        self.mode.setEnabled(True)
        self.seed.setEnabled(True)
        self.event.setEnabled(False)
        self.readings.setText("SYNTHETIC · Stopped; last simulated readings retained")
        self.frequency.live_frame = replace(
            self.frequency.live_frame, state="Demo stopped; last sample retained"
        )
        if self.frequency.source.currentIndex() == 0:
            self.frequency.select_frame()
