"""Spectrum workspace: direct measurements, explicit scope and frozen local snapshots."""

import math

import pyqtgraph as pg
from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QCheckBox,
    QColorDialog,
    QComboBox,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from bnkg.core.spectrum import SpectrumFrame


def nominal_frequency(frequency):
    decade = 10 ** math.floor(math.log10(frequency))
    return min(
        (x * decade for x in (1, 1.25, 1.6, 2, 2.5, 3.15, 4, 5, 6.3, 8, 10)),
        key=lambda value: abs(math.log(value / frequency)),
    )


def text_label(text):
    widget = QLabel(text)
    widget.setWordWrap(True)
    widget.setTextFormat(Qt.TextFormat.PlainText)
    return widget


class FrequencyPage(QWidget):
    palette_changed = Signal()

    def __init__(self, settings=None, *, demo=False):
        super().__init__()
        self.settings, self.demo = settings, demo
        self.live_frame = SpectrumFrame()
        self.saved_frame = None
        self.file_frame = None
        self.file_label = ""
        self.frame = self.live_frame
        self.spectra = {}
        self.visible_series = []
        self.bar_items = []
        self.cursor_index = None
        self.dark = True
        self.foreground = "#edf0e9"
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.heading = text_label(
            "DEMO SPECTRUM · Synthetic illustration"
            if demo
            else "FREQUENCY ANALYSIS · Instrument spectra"
        )
        self.heading.setObjectName("subheading")
        layout.addWidget(self.heading)
        controls = QGridLayout()
        self.source = QComboBox()
        self.source.addItems(["Live source", "Frozen snapshot", "Saved session"])
        self.source.setToolTip(
            "A local frozen snapshot is independent of new instrument readings. It lasts until replaced or the app closes; it is not a saved file."
        )
        self.source.setAccessibleName("Spectrum data source")
        self.freeze_button = QPushButton("Freeze live source")
        self.freeze_button.clicked.connect(self.freeze_current)
        self.source.currentIndexChanged.connect(self.select_frame)
        self.scope = QComboBox()
        for title, key in (
            ("All available quantities", "all"),
            ("Current time-weighted L", "current"),
            ("Whole-measurement Leq", "total"),
            ("Short-interval Leq", "interval"),
        ):
            self.scope.addItem(title, key)
        self.scope.setAccessibleName("Spectrum measurement scope")
        self.scope.currentIndexChanged.connect(self.refresh_selector)
        self.colors_button = QPushButton("Plot colors…")
        self.colors_button.clicked.connect(self.choose_color)
        self.selector = QComboBox()
        self.selector.setMinimumContentsLength(12)
        self.selector.setSizeAdjustPolicy(
            QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon
        )
        self.selector.setAccessibleName("Reference spectrum")
        self.selector.currentIndexChanged.connect(self.render)
        self.compare = QCheckBox("Compare A / C / Z")
        self.compare.setToolTip(
            "Compare only direct series with matching axes, units and measurement/time bases."
        )
        self.compare.setChecked(True)
        self.compare.toggled.connect(self.render)
        self.range = QComboBox()
        self.range.addItems(["Auto range", "20–90 dB", "20–140 dB"])
        self.range.setCurrentText(self.setting("spectrum_range", "Auto range"))
        self.range.setAccessibleName("Spectrum display range")
        self.range.currentTextChanged.connect(self.range_changed)
        controls.addWidget(self.source, 0, 0)
        controls.addWidget(self.freeze_button, 0, 1)
        controls.addWidget(self.scope, 1, 0)
        controls.addWidget(self.colors_button, 1, 1)
        controls.addWidget(self.selector, 2, 0, 1, 2)
        controls.addWidget(self.compare, 3, 0)
        controls.addWidget(self.range, 3, 1)
        controls.setColumnStretch(0, 1)
        controls.setColumnStretch(1, 1)
        layout.addLayout(controls)
        series_row = QHBoxLayout()
        self.weight_checks = {}
        for weight in ("Z", "C", "A"):
            check = QCheckBox(weight)
            check.setChecked(True)
            check.toggled.connect(self.render)
            series_row.addWidget(check)
            self.weight_checks[weight] = check
        series_row.addStretch()
        layout.addLayout(series_row)
        self.plot = pg.PlotWidget()
        self.plot.setMinimumHeight(160)
        self.plot.getAxis("bottom").setHeight(42)
        self.plot.getAxis("left").setWidth(62)
        self.plot.showGrid(y=True, alpha=0.15)
        self.plot.setMenuEnabled(False)
        self.plot.setMouseEnabled(x=False, y=False)
        self.cursor = pg.InfiniteLine(angle=90, movable=False, pen=pg.mkPen("#ba813e", width=1))
        self.plot.addItem(self.cursor)
        self.cursor.hide()
        self.plot.scene().sigMouseClicked.connect(self.pick_band)
        layout.addWidget(self.plot, 3)
        self.detail = text_label("Click a band for exact values.")
        layout.addWidget(self.detail)
        self.totals = text_label("Broadband values: unavailable")
        layout.addWidget(self.totals)
        self.table = QTableWidget(0, 0)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setMinimumHeight(100)
        self.table.horizontalHeader().setStretchLastSection(True)
        layout.addWidget(self.table, 2)
        self.notice = text_label("")
        self.notice.setObjectName("muted")
        layout.addWidget(self.notice)
        self.select_frame()

    def setting(self, key, default):
        return self.settings.value(key, default) if self.settings is not None else default

    def range_changed(self, value):
        if self.settings is not None and not self.demo:
            self.settings.setValue("spectrum_range", value)
        self.render()

    def series_color(self, weight):
        defaults = (
            {"A": "#83b8e8", "C": "#9acb89", "Z": "#eea191"}
            if self.dark
            else {"A": "#205c88", "C": "#286238", "Z": "#a33e2f"}
        )
        value = self.setting("spectrum_color_" + weight, defaults.get(weight, "#ba813e"))
        return value if QColor(value).isValid() else defaults.get(weight, "#ba813e")

    def choose_color(self):
        from PySide6.QtWidgets import QInputDialog

        weight, ok = QInputDialog.getItem(
            self, "Plot color", "Weighting", ["A", "C", "Z"], 0, False
        )
        if not ok:
            return
        color = QColorDialog.getColor(
            QColor(self.series_color(weight)), self, weight + " spectrum color"
        )
        if color.isValid() and self.settings is not None:
            self.settings.setValue("spectrum_color_" + weight, color.name())
            self.palette_changed.emit()
            self.render()

    def update_sample(self, sample):
        if sample.origin != ("simulation" if self.demo else "instrument"):
            return
        self.update_spectra(
            sample.spectra,
            broadband=sample.values,
            timestamp=sample.timestamp.isoformat(),
            state=sample.state,
            quality=sample.quality,
            measurement={
                k: sample.metadata[k]
                for k in ("MeasurementCounter", "StartTime", "StopTime", "ElapsedTime")
                if k in sample.metadata
            },
        )

    def update_spectra(self, spectra, **context):
        expected = "simulation" if self.demo else "instrument"
        spectra = {k: v for k, v in spectra.items() if v.get("origin") == expected}
        self.live_frame = SpectrumFrame.capture(spectra, **context)
        self.freeze_button.setEnabled(bool(self.live_frame.series))
        if self.source.currentIndex() == 0:
            self.select_frame()

    def freeze_current(self):
        if not self.live_frame.series:
            return
        self.saved_frame = self.live_frame
        self.source.setCurrentIndex(1)
        self.select_frame()

    def load_saved(self, frame, label):
        if self.demo or any(s.origin != "instrument" for s in frame.series):
            raise ValueError("Only saved instrument data can enter this Frequency view.")
        self.file_frame, self.file_label = frame, str(label)
        self.source.setCurrentIndex(2)
        self.select_frame()

    def select_frame(self):
        self.frame = (
            self.live_frame
            if self.source.currentIndex() == 0
            else (self.file_frame or SpectrumFrame())
            if self.source.currentIndex() == 2
            else (self.saved_frame or SpectrumFrame())
        )
        self.spectra = {s.key: s.as_dict() for s in self.frame.series}
        self.freeze_button.setEnabled(bool(self.live_frame.series))
        self.refresh_selector()

    def refresh_selector(self):
        old = self.selector.currentData()
        scope = self.scope.currentData()
        options = [s for s in self.frame.series if scope == "all" or s.meaning.kind == scope]
        self.selector.blockSignals(True)
        self.selector.clear()
        for series in options:
            self.selector.addItem(series.label, series.key)
        keys = [s.key for s in options]
        preferred = (
            old
            if old in keys
            else ("CPBLZF250ms" if "CPBLZF250ms" in keys else (keys[0] if keys else None))
        )
        self.selector.setCurrentIndex(self.selector.findData(preferred))
        self.selector.blockSignals(False)
        self.render()

    def render(self, *_):
        for item in self.bar_items:
            self.plot.removeItem(item)
        self.bar_items = []
        self.visible_series = []
        self.table.setRowCount(0)
        self.table.setColumnCount(0)
        anchor = next((s for s in self.frame.series if s.key == self.selector.currentData()), None)
        candidates = (
            [
                s
                for s in self.frame.series
                if s.key == anchor.key or (self.compare.isChecked() and anchor.compatible(s))
            ]
            if anchor
            else []
        )
        for weight, check in self.weight_checks.items():
            available = [s for s in candidates if s.meaning.weighting == weight]
            check.setEnabled(bool(available))
            check.setText(
                weight + (" · " + available[0].meaning.quantity if available else " · N/A")
            )
            check.setToolTip(
                "\n".join(s.label for s in available)
                or "No compatible direct instrument series; no substitute calculated."
            )
            check.setStyleSheet("color: " + self.series_color(weight) + ";" if available else "")
        self.visible_series = [
            s
            for s in candidates
            if s.meaning.weighting not in self.weight_checks
            or self.weight_checks[s.meaning.weighting].isChecked()
        ]
        source = "SYNTHETIC" if self.demo else "SLM"
        view = ("LIVE SOURCE", "FROZEN LOCAL SNAPSHOT", "SAVED SESSION")[self.source.currentIndex()]
        context = f"{source} · {view} · {self.frame.state or 'no state'} · {self.frame.timestamp or 'no sample time'}"
        if self.source.currentIndex() == 2:
            context += "\n" + (
                self.file_label or "Load a saved row from Sessions & export → Browse history."
            )
        if not anchor:
            self.detail.setText("No band selected.")
            self.totals.setText("Broadband values: unavailable")
            self.notice.setText(
                context
                + "\nNo supported spectrum for this selection. Interval Leq requires an explicitly verified integration window; it is not inferred from Fast weighting or refresh rate."
            )
            self.cursor.hide()
            self.plot.getAxis("bottom").setTicks([])
            return
        frequencies = anchor.frequencies
        self.plot.setLabel(
            "left",
            "Band level",
            units=anchor.descriptor.get("Unit", "unit unverified"),
            color=self.foreground,
        )
        valid = [v for s in self.visible_series for v in s.values if v is not None]
        fixed = self.range.currentIndex()
        low, high = (
            (20, 90)
            if fixed == 1
            else (20, 140)
            if fixed == 2
            else (math.floor((min(valid) - 5) / 10) * 10, math.ceil((max(valid) + 5) / 10) * 10)
            if valid
            else (0, 120)
        )
        self.plot.setYRange(low, max(low + 10, high), padding=0)
        self.plot.setXRange(-0.7, len(frequencies) - 0.3, padding=0)
        self.update_band_ticks()
        count = max(1, len(self.visible_series))
        for j, series in enumerate(self.visible_series):
            good = [(i, v) for i, v in enumerate(series.values) if v is not None]
            bar = pg.BarGraphItem(
                x=[i + (j - (count - 1) / 2) * 0.8 / count for i, _ in good],
                y0=low,
                height=[v - low for _, v in good],
                width=0.76 / count,
                brush=self.series_color(series.meaning.weighting),
                pen=None,
            )
            self.bar_items.append(bar)
            self.plot.addItem(bar)
        headers = ["Band Hz", "Exact Hz"] + [
            s.meaning.quantity + " dB" for s in self.visible_series
        ]
        self.table.setColumnCount(len(headers))
        self.table.setHorizontalHeaderLabels(headers)
        self.table.setRowCount(len(frequencies))
        for i, f in enumerate(frequencies):
            values = [f"{nominal_frequency(f):g}", f"{f:.3f}"] + [
                "—" if s.values[i] is None else f"{s.values[i]:.2f}" for s in self.visible_series
            ]
            for j, value in enumerate(values):
                item = QTableWidgetItem(value)
                if j >= 2:
                    item.setToolTip(self.visible_series[j - 2].label)
                self.table.setItem(i, j, item)
        self.table.setColumnWidth(0, 80)
        self.table.setColumnWidth(1, 90)
        broadband = dict(self.frame.broadband)
        totals = []
        for s in self.visible_series:
            # Only known cumulative/current scalar outputs can accompany these series.
            value = (
                broadband.get(s.meaning.quantity)
                if s.meaning.kind in {"current", "total"}
                else None
            )
            totals.append(
                s.meaning.quantity + ": " + ("unavailable" if value is None else f"{value:.2f} dB")
            )
        self.totals.setText(
            ("Synthetic broadband" if self.demo else "SLM broadband · not a band sum")
            + " · "
            + (" | ".join(totals) or "No series selected")
        )
        clipped = sum(v < low or v > high for v in valid)
        provenance = (
            "Synthetic illustration only."
            if self.demo
            else "Direct SLM values; no A/C/Z weighting synthesis. Missing bands are unavailable, not zero."
        )
        self.notice.setText(
            context
            + "\n"
            + anchor.meaning.label
            + ". "
            + provenance
            + (
                f" {clipped} values outside the display range; exact values remain in the table."
                if clipped
                else ""
            )
            + ("\n" + self.frame.quality if self.frame.quality else "")
        )
        self.show_band()

    def update_band_ticks(self):
        anchor = next((s for s in self.frame.series if s.key == self.selector.currentData()), None)
        if anchor is None:
            self.plot.getAxis("bottom").setTicks([])
            return
        frequencies = anchor.frequencies
        target = max(3, int((self.plot.width() - 70) / 65))
        stride = max(1, math.ceil(len(frequencies) / target))
        ticks = [
            (i, f"{nominal_frequency(f) / 1000:g}k" if f >= 1000 else f"{nominal_frequency(f):g}")
            for i, f in enumerate(frequencies)
        ]
        self.plot.getAxis("bottom").setTicks([ticks[::stride]])

    def resizeEvent(self, event):
        super().resizeEvent(event)
        QTimer.singleShot(0, self.update_band_ticks)

    def pick_band(self, event):
        if self.visible_series and self.plot.sceneBoundingRect().contains(event.scenePos()):
            point = self.plot.getViewBox().mapSceneToView(event.scenePos())
            self.cursor_index = max(
                0, min(len(self.visible_series[0].frequencies) - 1, round(point.x()))
            )
            self.show_band()

    def show_band(self):
        if self.cursor_index is None or not self.visible_series:
            self.cursor.hide()
            self.detail.setText(
                "Click a band for exact values. Legend and series selector identify the measurement scope."
            )
            return
        index = min(self.cursor_index, len(self.visible_series[0].frequencies) - 1)
        self.cursor.setPos(index)
        self.cursor.show()
        parts = [f"{nominal_frequency(self.visible_series[0].frequencies[index]):g} Hz"]
        for s in self.visible_series:
            value = s.values[index]
            parts.append(
                s.meaning.quantity + " " + ("unavailable" if value is None else f"{value:.2f} dB")
            )
        self.detail.setText(" · ".join(parts))

    def set_theme(self, background, foreground, accent):
        self.dark = QColor(background).lightness() < 128
        self.foreground = foreground
        self.plot.setBackground(background)
        for axis in ("left", "bottom"):
            self.plot.getAxis(axis).setTextPen(foreground)
            self.plot.getAxis(axis).setPen(foreground)
        self.plot.setLabel("left", "Band level", units="dB re 20 µPa", color=foreground)
        self.plot.setLabel("bottom", "Band centre", units="Hz", color=foreground)
        self.render()
