"""Independent cancellable history worker and read-only local browser."""

from pathlib import Path

from PySide6.QtCore import Qt, QThread, QTimer, Signal
from PySide6.QtWidgets import (
    QAbstractItemView,
    QBoxLayout,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from bnkg.core.history import read_page, read_sample
from bnkg.core.parameters import BY_ID
from bnkg.core.review import add_marker, read_review, save_review
from bnkg.core.spectrum import finite
from bnkg.core.trends import TrendPoint
from bnkg.ui.charts import TrendChart
from bnkg.ui.review import ReviewPanel, SavedSpectrumPreview


class HistoryQuery(QThread):
    result = Signal(object)
    failed = Signal(str)

    def __init__(self, mode, path, options, parent=None):
        super().__init__(parent)
        self.mode, self.path, self.options = mode, path, options

    def run(self):
        try:
            reader = {
                "sample": read_sample,
                "page": read_page,
                "marker": add_marker,
                "review_open": read_review,
                "review_save": save_review,
            }[self.mode]
            result = reader(self.path, **self.options, cancelled=self.isInterruptionRequested)
            if not self.isInterruptionRequested():
                self.result.emit(result)
        except Exception as exc:
            if not self.isInterruptionRequested():
                self.failed.emit(str(exc))


class HistoryBrowser(QWidget):
    idle = Signal()
    spectrum_selected = Signal(object, str)

    def __init__(self, session_dir):
        super().__init__()
        self.session_dir = str(session_dir)
        self.query = None
        self.page = None
        self.sample = None
        self.generation = 0
        self.path = ""
        self.jump_id = None
        self.selection_timer = QTimer(self)
        self.selection_timer.setSingleShot(True)
        self.selection_timer.setInterval(150)
        self.selection_timer.timeout.connect(self.inspect_selected)
        layout = QVBoxLayout(self)
        note = QLabel(
            "LOCAL HISTORY · Read-only saved BnKG sessions. Browsing does not pause monitoring or change the SLM. Times are PC receipt times; elapsed seconds are connection time, not the Leq integration period."
        )
        note.setWordWrap(True)
        layout.addWidget(note)
        row = QHBoxLayout()
        self.open = QPushButton("Browse local session…")
        self.open.clicked.connect(self.choose)
        self.refresh = QPushButton("Refresh")
        self.refresh.clicked.connect(lambda: self.open_path(self.path))
        self.cancel = QPushButton("Cancel operation")
        self.cancel.clicked.connect(self.stop)
        for button in (self.open, self.refresh, self.cancel):
            row.addWidget(button)
        layout.addLayout(row)
        self.info = QLabel("Select a SQLite session. No files are loaded automatically.")
        self.info.setTextFormat(Qt.TextFormat.PlainText)
        self.info.setWordWrap(True)
        layout.addWidget(self.info)
        self.table = QTableWidget(0, 7)
        self.table.setHorizontalHeaderLabels(
            ["Sample", "PC UTC receipt", "Elapsed s", "State", "Origin", "LAF dB", "LAeq dB"]
        )
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.itemSelectionChanged.connect(self.selection_changed)
        self.chart = TrendChart("Saved history page")
        self.chart.point_selected.connect(lambda point: self.select_id(point.record_id))
        self.saved_spectrum = SavedSpectrumPreview()
        self.review_panel = ReviewPanel()
        self.review_panel.request.connect(self.review_request)
        self.review_panel.changed.connect(self.update_markers)
        self.review_panel.jump_requested.connect(self.select_id)
        review_content = QWidget()
        review_layout = self.review_layout = QVBoxLayout(review_content)
        review_layout.setContentsMargins(0, 0, 0, 0)
        self.chart.setMinimumHeight(540)
        self.chart.plot.setMaximumHeight(240)
        self.saved_spectrum.setMinimumHeight(280)
        review_layout.addWidget(self.chart, 2)
        review_layout.addWidget(self.saved_spectrum, 1)
        self.review_scroll = QScrollArea()
        self.review_scroll.setWidgetResizable(True)
        self.review_scroll.setWidget(review_content)
        self.marker_scroll = QScrollArea()
        self.marker_scroll.setWidgetResizable(True)
        self.review_panel.setMinimumHeight(500)
        self.marker_scroll.setWidget(self.review_panel)

        self.data_tabs = QTabWidget()
        self.data_tabs.addTab(self.table, "Rows")
        self.data_tabs.addTab(self.review_scroll, "Chart this page")
        self.data_tabs.addTab(self.marker_scroll, "Review markers")
        layout.addWidget(self.data_tabs, 2)
        pages = QHBoxLayout()
        self.previous = QPushButton("Previous 100")
        self.next = QPushButton("Next 100")
        self.previous.clicked.connect(lambda: self.turn_page(False))
        self.next.clicked.connect(lambda: self.turn_page(True))
        self.inspect = QPushButton("Inspect selected sample")
        self.inspect.clicked.connect(self.inspect_selected)
        for button in (self.previous, self.next, self.inspect):
            pages.addWidget(button)
        layout.addLayout(pages)
        self.details = QLabel(
            "Select a row and inspect it to review its recorded values and spectrum availability."
        )
        self.details.setTextFormat(Qt.TextFormat.PlainText)
        self.details.setWordWrap(True)
        detail_page = QWidget()
        detail_layout = QVBoxLayout(detail_page)
        detail_layout.addWidget(self.details)
        self.values = QTableWidget(0, 2)
        self.values.setHorizontalHeaderLabels(["Recorded parameter", "Value (dB)"])
        self.values.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.values.horizontalHeader().setStretchLastSection(True)
        self.values.setColumnWidth(0, 260)
        detail_layout.addWidget(self.values, 1)
        self.data_tabs.addTab(detail_page, "Selected values")
        self.load = QPushButton("Load saved spectrum in Frequency")
        self.load.clicked.connect(self.load_spectrum)
        layout.addWidget(self.load)
        self.update_buttons()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        narrow = self.width() < 600
        self.review_layout.setDirection(
            QBoxLayout.Direction.LeftToRight
            if self.width() >= 900
            else QBoxLayout.Direction.TopToBottom
        )
        self.chart.setMinimumHeight(580 if narrow else 540)
        self.saved_spectrum.setMinimumHeight(330 if narrow else 280)

    def choose(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Browse BnKG session", self.session_dir, "BnKG sessions (*.sqlite)"
        )
        if path:
            self.open_path(path)

    def open_path(self, path):
        if self.query or not path:
            return
        if not self.review_panel.confirm_discard():
            return
        self.selection_timer.stop()
        self.review_panel.reset()
        self.update_markers()
        self.path = str(path)
        self.page = None
        self.table.setRowCount(0)
        self.chart.set_points([])
        self.clear_sample()
        self.fetch("page", {})

    def fetch(self, mode, options):
        if self.query:
            return
        self.selection_timer.stop()
        generation = self.generation
        self.query = HistoryQuery(mode, self.path, options, self)
        self.query.result.connect(
            lambda result: self.loaded(mode, result) if generation == self.generation else None
        )
        self.query.failed.connect(
            lambda message: self.info.setText(message) if generation == self.generation else None
        )
        self.query.finished.connect(self.finished)
        self.info.setText(
            "Reading local session…" if mode in ("page", "sample") else "Verifying local review…"
        )
        self.update_buttons()
        self.query.start()

    def loaded(self, mode, result):
        if mode == "page":
            self.page = result
            self.clear_sample()
            self.table.blockSignals(True)
            self.table.clearSelection()
            self.table.setCurrentCell(-1, -1)
            self.chart.set_points(
                [
                    TrendPoint.create(
                        row.timestamp, dict(row.values), row.origin, row.state, row.quality, row.id
                    )
                    for row in result.rows
                ],
                "Saved page · " + Path(result.path).name,
            )
            self.table.setRowCount(len(result.rows))
            for i, row in enumerate(result.rows):
                fields = (
                    row.id,
                    row.timestamp,
                    row.elapsed,
                    row.state,
                    row.origin,
                    row.laf,
                    row.laeq,
                )
                for j, value in enumerate(fields):
                    item = QTableWidgetItem("—" if value is None else str(value))
                    item.setToolTip(row.quality)
                    self.table.setItem(i, j, item)
            self.table.blockSignals(False)
            self.update_markers()
            self.table.setColumnWidth(1, 225)
            meta = dict(result.metadata)
            self.info.setText(
                f"{result.path}\nSession {meta['session_id']} · {meta['origin']} · {len(result.rows)} rows on this page · snapshot through sample {result.ceiling}. Refresh to include new rows."
            )
        elif mode == "sample":
            self.sample = result
            self.saved_spectrum.set_sample(result)
            self.details.setText(
                result.label + "\n" + result.explanation + "\n" + result.row.quality
            )
            if any(BY_ID.get(key) and BY_ID[key].formula for key, _ in result.values):
                self.details.setText(
                    self.details.text()
                    + "\nCalculated fields are recorded local results, not direct SLM outputs; they are not recomputed here."
                )
            self.values.setRowCount(len(result.values))
            for i, (key, value) in enumerate(result.values):
                parameter = BY_ID.get(key)
                item = QTableWidgetItem(
                    key + (" · Calculated" if parameter and parameter.formula else "")
                )
                if parameter:
                    item.setToolTip(parameter.formula or parameter.description)
                self.values.setItem(i, 0, item)
                self.values.setItem(
                    i, 1, QTableWidgetItem(f"{value:.3f}" if finite(value) else "Unavailable")
                )
            self.info.setText("Saved sample loaded locally; source file unchanged.")
        else:
            self.review_panel.completed(mode, result)
            self.info.setText(
                "Local review snapshot saved: " + result
                if mode == "review_save"
                else "Local review updated. Original session unchanged; Exclude is a review label only."
            )
        self.update_buttons()

    def clear_sample(self):
        self.selection_timer.stop()
        self.sample = None
        self.saved_spectrum.set_sample(None)
        self.values.setRowCount(0)
        self.details.setText(
            "Inspect the selected row. Missing descriptors or unknown origins are not guessed."
        )
        if hasattr(self, "load"):
            self.update_buttons()

    def selection_changed(self):
        self.clear_sample()
        row = self.table.currentRow()
        ident = self.page.rows[row].id if self.page and 0 <= row < len(self.page.rows) else None
        self.chart.select_record(ident)
        self.update_buttons()
        if ident is not None and self.query is None:
            self.selection_timer.start()

    def select_id(self, ident):
        if self.query or not self.page or ident is None:
            return
        for i, row in enumerate(self.page.rows):
            if row.id == ident:
                self.table.selectRow(i)
                self.table.scrollToItem(self.table.item(i, 0))
                return
        if ident <= self.page.ceiling:
            self.jump_id = ident
            self.clear_sample()
            self.fetch(
                "page",
                {
                    "after": ident - 1,
                    "ceiling": self.page.ceiling,
                    "expected_session": dict(self.page.metadata)["session_id"],
                },
            )
        else:
            self.info.setText(
                "Marker is beyond this snapshot. Save the review, refresh the session, then reopen the review."
            )

    def review_request(self, mode, options):
        if self.page and not self.query:
            self.fetch(
                mode, {**options, "expected_session": dict(self.page.metadata)["session_id"]}
            )

    def update_markers(self):
        review = self.review_panel.review
        self.chart.set_markers(review.markers if review else ())

    def turn_page(self, forward):
        if self.page and self.page.rows and not self.query:
            options = {
                "ceiling": self.page.ceiling,
                "expected_session": dict(self.page.metadata)["session_id"],
            }
            options["after" if forward else "before"] = self.page.rows[-1 if forward else 0].id
            self.clear_sample()
            self.fetch("page", options)

    def inspect_selected(self):
        row = self.table.currentRow()
        if self.page and 0 <= row < len(self.page.rows) and not self.query:
            self.clear_sample()
            self.fetch(
                "sample",
                {
                    "ident": self.page.rows[row].id,
                    "expected_session": dict(self.page.metadata)["session_id"],
                },
            )

    def load_spectrum(self):
        if self.sample and self.sample.frame is not None and not self.query:
            self.spectrum_selected.emit(self.sample.frame, self.sample.label)

    def stop(self):
        self.selection_timer.stop()
        self.jump_id = None
        self.generation += 1
        if self.query:
            self.query.requestInterruption()
            self.info.setText("Cancelling local operation…")

    def finished(self):
        cancelled = self.query.isInterruptionRequested()
        self.query.deleteLater()
        self.query = None
        if cancelled:
            self.info.setText(
                "Local operation cancelled. Original session unchanged; a review snapshot already published is retained."
            )
        self.update_buttons()
        if self.jump_id is not None:
            ident, self.jump_id = self.jump_id, None
            if self.page and any(row.id == ident for row in self.page.rows):
                self.select_id(ident)
            else:
                self.info.setText(
                    "Marked row could not be loaded. Reopen and verify the review against the current session."
                )
        self.idle.emit()

    def update_buttons(self):
        ready = self.query is None
        self.open.setEnabled(ready)
        self.refresh.setEnabled(ready and bool(self.path))
        self.cancel.setEnabled(not ready)
        self.table.setEnabled(ready)
        self.chart.setEnabled(ready)
        row = self.table.currentRow()
        ident = self.page.rows[row].id if self.page and 0 <= row < len(self.page.rows) else None
        self.review_panel.context(self.page, ident, ready)
        self.previous.setEnabled(ready and self.page is not None and self.page.previous)
        self.next.setEnabled(ready and self.page is not None and self.page.following)
        self.inspect.setEnabled(ready and self.table.currentRow() >= 0)
        self.load.setEnabled(ready and self.sample is not None and self.sample.frame is not None)
