"""Shared presentation widgets; no acquisition or device configuration."""

from enum import IntEnum

import pyqtgraph as pg
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QProgressBar, QVBoxLayout

from bnkg.core.spectrum import finite


class Page(IntEnum):
    DASHBOARD = 0
    SLM = 1
    PARAMETERS = 2
    DATA = 3
    SESSIONS = 4
    CONNECTION = 5
    DEVICE_FILES = 6
    ABOUT = 7
    FREQUENCY = 8
    METADATA = 9
    DEMO = 10


def parameter_scope(key):
    if key in {"LAF", "LCF", "LZF"}:
        return "Current Fast"
    if key in {"LAS", "LCS", "LZS"}:
        return "Current Slow"
    if key in {"LAeq", "LCeq", "LZeq", "LAIeq", "LAFeq", "LAFTeq"}:
        return "Whole-measurement equivalent level"
    if key.endswith(("min", "max")):
        return "Measurement minimum" if key.endswith("min") else "Measurement maximum"
    if key.endswith("peak"):
        return "Peak level; not a Fast level"
    if key in {"L10", "L50", "L90"} or key.startswith("LN"):
        return "Configured percentile basis"
    if key in {"LAE", "LCE", "LZE"}:
        return "Sound exposure level"
    if key == "StdDev":
        return "Configured statistics basis"
    return "See parameter description"


class ParameterTile(QFrame):
    def __init__(self, label, description, derived=False):
        super().__init__()
        self.setObjectName("tile")
        self.setMinimumHeight(116)
        self.setToolTip(description)
        layout = QVBoxLayout(self)
        self.caption = QLabel(label + (" · Calculated" if derived else ""))
        self.caption.setObjectName("muted")
        self.value = QLabel("—")
        self.value.setObjectName("reading")
        self.value.setAccessibleName(label + " reading")
        row = QHBoxLayout()
        row.addWidget(self.value)
        row.addStretch()
        unit = QLabel("dB")
        unit.setObjectName("muted")
        row.addWidget(unit, alignment=Qt.AlignmentFlag.AlignBottom)
        layout.addWidget(self.caption)
        layout.addLayout(row)
        self.scope = QLabel("Calculated" if derived else parameter_scope(label))
        self.scope.setWordWrap(True)
        self.scope.setObjectName("muted")
        layout.addWidget(self.scope)


class LevelBar(QFrame):
    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.label = QLabel("LAF · Current Fast · unavailable")
        self.label.setWordWrap(True)
        layout.addWidget(self.label)
        self.bar = QProgressBar()
        self.bar.setRange(0, 1000)
        self.bar.setTextVisible(False)
        self.bar.setMaximumHeight(12)
        layout.addWidget(self.bar)
        self.update_level(None)

    def update_level(self, value, extended=True):
        low, high = 20, 140 if extended else 90
        valid = finite(value)
        self.bar.setEnabled(valid)
        self.bar.setValue(
            round(max(0, min(1, (value - low) / (high - low))) * 1000) if valid else 0
        )
        reading = f"{value:.1f} dB" if valid else "unavailable"
        outside = " · outside display range" if valid and not low <= value <= high else ""
        self.label.setText(f"LAF · Current Fast · {reading} · display {low}–{high} dB{outside}")
        self.setToolTip(
            "Local display scale only. This is not an exposure limit or alarm threshold."
        )


class SpectrumPreview(QFrame):
    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.info = QLabel("Current SLM spectrum · unavailable")
        self.info.setWordWrap(True)
        self.info.setTextFormat(Qt.TextFormat.PlainText)
        layout.addWidget(self.info)
        self.plot = pg.PlotWidget()
        self.plot.setMinimumHeight(160)
        self.plot.setMaximumHeight(200)
        self.plot.setMouseEnabled(x=False, y=False)
        self.plot.setMenuEnabled(False)
        self.plot.showGrid(y=True, alpha=0.15)
        layout.addWidget(self.plot)
        self.accent = "#a6d39a"
        self.foreground = "#edf0e9"
        self.frame = None

    def update_frame(self, frame):
        self.frame = frame
        self.plot.clear()
        candidates = [
            s for s in frame.series if s.origin == "instrument" and s.meaning.kind == "current"
        ]
        series = next(
            (s for s in candidates if s.meaning.quantity == "LZF"), next(iter(candidates), None)
        )
        self.show_series(series)

    def show_series(self, series):
        self.plot.clear()
        if series is None:
            self.info.setText("Current SLM spectrum · unavailable; no calculated substitute")
            self.plot.getAxis("bottom").setTicks([])
            return
        self.info.setText(series.label)
        self.plot.setLabel(
            "left",
            "Band level",
            units=series.descriptor.get("Unit", "unit unverified"),
            color=self.foreground,
        )
        good = [(i, v) for i, v in enumerate(series.values) if v is not None]
        low = min((v for _, v in good), default=0) - 5
        high = max((v for _, v in good), default=100) + 5
        self.plot.addItem(
            pg.BarGraphItem(
                x=[i for i, _ in good],
                y0=low,
                height=[v - low for _, v in good],
                width=0.8,
                brush=self.accent,
                pen=None,
            )
        )
        self.plot.setYRange(low, high, padding=0)
        self.plot.setXRange(-0.7, len(series.values) - 0.3, padding=0)
        from bnkg.ui.frequency import nominal_frequency

        ticks = [(i, f"{nominal_frequency(f):g}") for i, f in enumerate(series.frequencies)]
        self.plot.getAxis("bottom").setTicks([ticks[:: max(1, len(ticks) // 8)]])

    def set_theme(self, background, foreground, accent):
        self.accent = accent
        self.foreground = foreground
        self.plot.setBackground(background)
        for axis in ("left", "bottom"):
            self.plot.getAxis(axis).setTextPen(foreground)
            self.plot.getAxis(axis).setPen(foreground)
        self.plot.setLabel("left", "Band level", units="dB re 20 µPa", color=foreground)
        self.plot.setLabel("bottom", "Band centre", units="Hz", color=foreground)
        if self.frame is not None:
            self.update_frame(self.frame)
