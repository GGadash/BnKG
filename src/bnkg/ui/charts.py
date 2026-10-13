"""Reusable bounded multi-series charts for captured or historical values."""

import math
from collections import deque
from datetime import UTC, datetime

import pyqtgraph as pg
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QComboBox, QGridLayout, QLabel, QVBoxLayout, QWidget

from bnkg.core.parameters import BY_ID, PARAMETERS
from bnkg.core.trends import series_points
from bnkg.ui.presentation import parameter_scope


class TrendChart(QWidget):
    point_selected = Signal(object)

    def __init__(self, source="Captured instrument samples"):
        super().__init__()
        self.points = deque(maxlen=100)
        self.source_label = source
        self.cursor_point = None
        self.markers = ()
        layout = QVBoxLayout(self)
        self.notice = QLabel(
            source
            + ". PC UTC receipt times, not integration intervals. Missing values, source/clock changes and gaps over 3 s are not joined. Points are recorded values; no resampling or acoustic averaging."
        )
        self.notice.setWordWrap(True)
        self.notice.setTextFormat(Qt.TextFormat.PlainText)
        layout.addWidget(self.notice)
        controls = QGridLayout()
        self.selectors = []
        for i, initial in enumerate(("LAF", "LAeq", "LCpeak")):
            combo = QComboBox()
            combo.addItem("None", "")
            for p in PARAMETERS:
                scope = "Calculated: " + p.formula if p.formula else parameter_scope(p.id)
                combo.addItem(p.id + " · " + scope, p.id)
                combo.setItemData(combo.count() - 1, p.description, Qt.ItemDataRole.ToolTipRole)
            combo.setMinimumContentsLength(5)
            combo.setSizeAdjustPolicy(
                QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon
            )
            combo.setCurrentIndex(combo.findData(initial))
            combo.currentIndexChanged.connect(self.render)
            controls.addWidget(combo, i, 0)
            self.selectors.append(combo)
        self.window = QComboBox()
        for text, seconds in (
            ("All retained", 0),
            ("Last 30 seconds", 30),
            ("Last 2 minutes", 120),
            ("Last 10 minutes", 600),
        ):
            self.window.addItem(text, seconds)
        self.window.currentIndexChanged.connect(self.render)
        controls.addWidget(self.window, 0, 1)
        layout.addLayout(controls)
        self.plot = pg.PlotWidget(axisItems={"bottom": pg.DateAxisItem(utcOffset=0)})
        self.plot.setMinimumHeight(180)
        self.plot.setMenuEnabled(False)
        self.plot.showGrid(x=True, y=True, alpha=0.15)
        self.legend = self.plot.addLegend(offset=(10, 10))
        self.cursor = pg.InfiniteLine(angle=90, movable=False)
        self.plot.addItem(self.cursor)
        self.cursor.hide()
        self.plot.scene().sigMouseClicked.connect(self.pick)
        self.curves = []
        self.colors = ["#a6d39a", "#8dc6ed", "#e7b66f"]
        layout.addWidget(self.plot, 1)
        self.marker_plot = pg.PlotWidget()
        self.marker_plot.setFixedHeight(100)
        self.marker_plot.setMenuEnabled(False)
        self.marker_plot.setMouseEnabled(x=False, y=False)
        self.marker_plot.setXLink(self.plot)
        self.marker_plot.getAxis("left").setTicks(
            [[(i, k) for i, k in enumerate(("M1", "M2", "M3", "Exclude"), 1)]]
        )
        self.marker_plot.getAxis("bottom").setStyle(showValues=False)
        self.marker_plot.setYRange(0.5, 4.5, padding=0)
        self.marker_plot.hide()
        layout.addWidget(self.marker_plot)
        self.detail = QLabel("Click a point to inspect its recorded time, values and quality.")
        self.detail.setWordWrap(True)
        self.detail.setTextFormat(Qt.TextFormat.PlainText)
        layout.addWidget(self.detail)
        self.visible_points = []

    def set_limit(self, limit):
        self.points = deque(self.points, maxlen=max(1, min(999, limit)))
        self.render()

    def append(self, point):
        if point is not None:
            self.points.append(point)
        self.render()

    def set_points(self, points, source=None):
        self.points = deque((p for p in points if p is not None), maxlen=self.points.maxlen)
        if source:
            self.source_label = source
        self.cursor_point = None
        self.render()

    def render(self, *_):
        for curve in self.curves:
            self.plot.removeItem(curve)
        self.curves = []
        self.legend.clear()
        selected = self.cursor_point
        self.cursor.hide()
        points = list(self.points)
        window = self.window.currentData()
        if points and window:
            latest = max(p.timestamp for p in points)
            points = [p for p in points if p.timestamp >= latest - window]
        self.visible_points = points
        seen = set()
        for i, selector in enumerate(self.selectors):
            key = selector.currentData()
            if not key or key in seen:
                continue
            seen.add(key)
            p = BY_ID[key]
            name = (
                p.id + " · " + ("Calculated: " + p.formula if p.formula else parameter_scope(key))
            )
            x, y = series_points(points, key)
            if not any(math.isfinite(v) for v in y):
                x, y = [], []  # Keep the legend without asking Qt to bound an all-NaN curve.
            curve = self.plot.plot(
                x,
                y,
                pen=pg.mkPen(self.colors[i], width=2),
                symbol="o",
                symbolSize=4,
                symbolBrush=self.colors[i],
                symbolPen=None,
                connect="finite",
                name=name,
            )
            self.curves.append(curve)
        origins = ", ".join(sorted({p.origin for p in points})) or "no data"
        self.notice.setText(
            f"{self.source_label} · {len(points)} displayed / {len(self.points)} retained · {origins}. PC UTC receipt times, not integration intervals. Missing values and source/clock changes or gaps >3 s break lines. No resampling or acoustic averaging."
        )
        self.render_markers()
        if selected in points:
            self.select_point(selected)
        else:
            self.cursor_point = None
            self.cursor.hide()
            self.detail.setText("Click a point to inspect its recorded time, values and quality.")

    def pick(self, event):
        if not self.visible_points or not self.plot.sceneBoundingRect().contains(event.scenePos()):
            return
        x = self.plot.getViewBox().mapSceneToView(event.scenePos()).x()
        point = min(self.visible_points, key=lambda p: abs(p.timestamp - x))
        self.select_point(point, emit=True)

    def select_record(self, ident):
        point = next((p for p in self.visible_points if p.record_id == ident), None)
        self.select_point(point)

    def select_point(self, point, *, emit=False):
        self.cursor_point = point
        if point is None:
            self.cursor.hide()
            self.detail.setText(
                "Selected row has no plotted timestamp or is outside the chart window."
            )
            return
        self.cursor.setPos(point.timestamp)
        self.cursor.show()
        values = dict(point.values)
        parts = []
        for selector in self.selectors:
            key = selector.currentData()
            if key:
                value = values.get(key)
                parts.append(key + ": " + ("unavailable" if value is None else f"{value:.2f} dB"))
        self.detail.setText(
            (f"Sample {point.record_id} · " if point.record_id is not None else "")
            + datetime.fromtimestamp(point.timestamp, UTC).isoformat()
            + " · "
            + point.origin
            + " · "
            + point.state
            + "\n"
            + " | ".join(parts)
            + "\n"
            + point.quality
        )

        if emit:
            self.point_selected.emit(point)

    def set_markers(self, markers):
        self.markers = markers
        self.render_markers()

    def render_markers(self):
        self.marker_plot.clear()
        self.marker_plot.setVisible(bool(self.markers))
        if not self.markers:
            return
        kinds = ("M1", "M2", "M3", "Exclude")
        points = {p.record_id: p for p in self.visible_points}
        spots = {}
        for marker in self.markers:
            for ref in marker.rows:
                if ref.id in points:
                    key = (marker.kind, ref.id)
                    spots[key] = {
                        "pos": (points[ref.id].timestamp, kinds.index(marker.kind) + 1),
                        "data": ref.id,
                    }
        scatter = pg.ScatterPlotItem(
            list(spots.values()), symbol="s", size=8, brush=self.colors[0], pen=None
        )
        scatter.sigClicked.connect(lambda _, hits: self.select_record_from_marker(hits))
        self.marker_plot.addItem(scatter)

    def select_record_from_marker(self, hits):
        if hits:
            point = next((p for p in self.visible_points if p.record_id == hits[0].data()), None)
            if point:
                self.select_point(point, emit=True)

    def set_theme(self, background, foreground, accent):
        from PySide6.QtGui import QColor

        dark = QColor(background).lightness() < 128
        self.colors = [accent, "#8dc6ed" if dark else "#205c88", "#e7b66f" if dark else "#885208"]
        self.marker_plot.setBackground(background)
        for axis in ("left", "bottom"):
            self.marker_plot.getAxis(axis).setPen(foreground)
            self.marker_plot.getAxis(axis).setTextPen(foreground)
        self.plot.setBackground(background)
        for axis in ("left", "bottom"):
            self.plot.getAxis(axis).setPen(foreground)
            self.plot.getAxis(axis).setTextPen(foreground)
        self.plot.setLabel("left", "Recorded level", units="dB", color=foreground)
        self.plot.setLabel("bottom", "PC receipt time (UTC)", color=foreground)
        self.legend.setLabelTextColor(foreground)
        self.render()
