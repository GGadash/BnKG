"""Local review controls and compact descriptor-backed saved spectrum."""

from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QFileDialog,
    QGridLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from bnkg.core.review import BASIS, KINDS
from bnkg.ui.presentation import SpectrumPreview


class SavedSpectrumPreview(QWidget):
    def __init__(self):
        super().__init__()
        self.sample = None
        layout = QVBoxLayout(self)
        self.selector = QComboBox()
        self.selector.setMinimumContentsLength(10)
        self.selector.setSizeAdjustPolicy(
            QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon
        )
        self.selector.setAccessibleName("Selected saved-row spectrum")
        self.selector.currentIndexChanged.connect(self.render)
        layout.addWidget(self.selector)
        self.preview = SpectrumPreview()
        layout.addWidget(self.preview)
        self.set_sample(None)

    def set_sample(self, sample):
        previous = self.selector.currentText()
        self.sample = sample
        self.selector.blockSignals(True)
        self.selector.clear()
        if sample and sample.frame:
            for series in sample.frame.series:
                self.selector.addItem(series.label)
        if self.selector.findText(previous) >= 0:
            self.selector.setCurrentText(previous)
        self.selector.blockSignals(False)
        self.render()

    def render(self, *_):
        index = self.selector.currentIndex()
        series = (
            self.sample.frame.series[index]
            if self.sample and self.sample.frame and index >= 0
            else None
        )
        self.preview.show_series(series)
        if series:
            self.preview.info.setText(
                f"Saved sample {self.sample.row.id} · {self.sample.row.timestamp}\n" + series.label
            )
        else:
            self.preview.info.setText(
                "Saved spectrum unavailable. "
                + (
                    self.sample.explanation
                    if self.sample
                    else "Select a saved row; its own context will be read."
                )
            )

    def set_theme(self, background, foreground, accent):
        self.preview.set_theme(background, foreground, accent)
        self.render()


class ReviewPanel(QWidget):
    request = Signal(str, object)
    changed = Signal()
    jump_requested = Signal(int)

    def __init__(self):
        super().__init__()
        self.review = None
        self.dirty = False
        self.anchor = None
        self.page = None
        self.selected = None
        self.ready = True
        self.saved_path = ""
        layout = QVBoxLayout(self)
        note = QLabel(
            BASIS
            + " Marker ribbons show marked recorded points, not continuous intervals. Duplicate timestamps overlap; use Rows for exact selection."
        )
        note.setWordWrap(True)
        layout.addWidget(note)
        grid = QGridLayout()
        self.kind = QComboBox()
        self.kind.addItems(KINDS)
        self.note = QLineEdit()
        self.note.setMaxLength(500)
        self.note.setPlaceholderText("Optional local note (up to 500 characters)")
        self.start = QPushButton("Set range start")
        self.start.clicked.connect(self.set_anchor)
        self.clear = QPushButton("Use single row")
        self.clear.clicked.connect(self.clear_anchor)
        self.add = QPushButton("Add marker")
        self.add.clicked.connect(self.add_marker)
        self.open = QPushButton("Open review…")
        self.open.clicked.connect(self.open_review)
        self.save = QPushButton("Save review as…")
        self.save.clicked.connect(self.save_review)
        for i, widget in enumerate(
            (self.kind, self.note, self.start, self.clear, self.add, self.open, self.save)
        ):
            grid.addWidget(widget, i // 2, i % 2)
        layout.addLayout(grid)
        self.status = QLabel()
        self.status.setWordWrap(True)
        self.status.setTextFormat(Qt.TextFormat.PlainText)
        layout.addWidget(self.status)
        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels(["Local marker", "Sample IDs", "Rows", "Note"])
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.horizontalHeader().setStretchLastSection(True)
        for index, width in enumerate((85, 105, 55)):
            self.table.setColumnWidth(index, width)
        self.table.itemSelectionChanged.connect(self.update_controls)
        self.table.cellDoubleClicked.connect(lambda *_: self.jump())
        layout.addWidget(self.table)
        self.goto = QPushButton("Go to marker first row")
        self.goto.clicked.connect(self.jump)
        layout.addWidget(self.goto)
        self.remove = QPushButton("Remove selected local marker")
        self.remove.clicked.connect(self.remove_marker)
        layout.addWidget(self.remove)
        self.update_controls()

    def confirm_discard(self):
        if not self.dirty:
            return True
        return (
            QMessageBox.question(
                self,
                "Unsaved local review",
                "Discard unsaved marker changes? Choose No to return and Save review as… first.",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            == QMessageBox.StandardButton.Yes
        )

    def reset(self):
        self.review, self.anchor, self.selected, self.page = None, None, None, None
        self.dirty, self.saved_path = False, ""
        self.render()

    def context(self, page, selected, ready):
        self.page, self.selected, self.ready = page, selected, ready
        if page is None or self.anchor not in {row.id for row in page.rows}:
            self.anchor = None
        self.update_controls()

    def set_anchor(self):
        self.anchor = self.selected
        self.update_controls()

    def clear_anchor(self):
        self.anchor = None
        self.update_controls()

    def add_marker(self):
        if not self.ready or self.page is None or self.selected is None:
            return
        low, high = sorted((self.anchor or self.selected, self.selected))
        ids = [row.id for row in self.page.rows if low <= row.id <= high]
        self.request.emit(
            "marker",
            {
                "review": self.review,
                "ids": ids,
                "kind": self.kind.currentText(),
                "note": self.note.text(),
            },
        )

    def open_review(self):
        if not self.confirm_discard():
            return
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Open local review snapshot",
            str(Path(self.page.path).parent),
            "BnKG review (*.bnkg-review.json)",
        )
        if path:
            self.request.emit("review_open", {"target": path})

    def save_review(self):
        default = (
            str(Path(self.page.path).with_suffix(""))
            + "-"
            + datetime.now(UTC).strftime("%Y%m%dT%H%M%S%fZ")
            + ".bnkg-review.json"
        )
        path, _ = QFileDialog.getSaveFileName(
            self, "Save a new review snapshot", default, "BnKG review (*.bnkg-review.json)"
        )
        if path:
            self.request.emit("review_save", {"target": path, "review": self.review})

    def completed(self, mode, result):
        if mode == "review_save":
            self.saved_path, self.dirty = result, False
        else:
            self.review, self.dirty = result, mode == "marker"
            self.saved_path = "" if mode == "review_open" else self.saved_path
            if mode == "marker":
                self.note.clear()
        self.render()
        self.changed.emit()

    def remove_marker(self):
        index = self.table.currentRow()
        if self.ready and self.review and index >= 0:
            self.review = replace(
                self.review, markers=self.review.markers[:index] + self.review.markers[index + 1 :]
            )
            self.dirty = True
            self.render()
            self.changed.emit()

    def jump(self):
        index = self.table.currentRow()
        if self.ready and self.review and index >= 0:
            self.jump_requested.emit(self.review.markers[index].rows[0].id)

    def render(self):
        markers = self.review.markers if self.review else ()
        self.table.setRowCount(len(markers))
        for i, marker in enumerate(markers):
            for j, text in enumerate(
                (
                    marker.kind,
                    f"{marker.rows[0].id}–{marker.rows[-1].id}",
                    str(len(marker.rows)),
                    marker.note,
                )
            ):
                item = QTableWidgetItem(text)
                item.setToolTip(
                    "Local annotation created "
                    + marker.created_utc
                    + "; exact row membership verified on save/open."
                )
                self.table.setItem(i, j, item)
        self.update_controls()

    def update_controls(self):
        selected = self.ready and self.page is not None and self.selected is not None
        for button in (self.start, self.add):
            button.setEnabled(selected)
        self.clear.setEnabled(self.ready and self.anchor is not None)
        self.open.setEnabled(self.ready and self.page is not None)
        self.save.setEnabled(self.ready and self.review is not None)
        self.table.setEnabled(self.ready)
        for button in (self.goto, self.remove):
            button.setEnabled(
                self.ready and self.review is not None and self.table.currentRow() >= 0
            )
        selection = (
            f"Selected sample {self.selected}"
            if self.selected is not None
            else "Select a saved row"
        )
        if self.anchor is not None:
            selection += f" · range starts at sample {self.anchor} (current page only)"
        count = len(self.review.markers) if self.review else 0
        self.status.setText(
            f"{selection}. {count}/128 markers; at most 1,000 row references.\n"
            + (
                "Unsaved changes — save a separate review snapshot."
                if self.dirty
                else "Review snapshot unchanged."
                if self.review
                else "No review loaded."
            )
            + ("\nSaved: " + self.saved_path if self.saved_path else "")
        )
