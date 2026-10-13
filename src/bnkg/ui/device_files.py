"""Explicit asynchronous saved-file inventory with bounded visible pages."""

from pathlib import Path
from urllib.parse import unquote

from PySide6.QtCore import QDate, Qt, QThread, Signal
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QDateEdit,
    QFileDialog,
    QGridLayout,
    QLabel,
    QPushButton,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from bnkg.core.device_files import DATA, DeviceFilesClient


class FileQuery(QThread):
    result = Signal(object, object, object)
    failed = Signal(str)

    def __init__(self, connection, directories, request, parent=None):
        super().__init__(parent)
        self.connection = connection
        self.directories = set(directories)
        self.request = request

    def run(self):
        client = None
        try:
            client = DeviceFilesClient(**self.connection)
            client.directories.update(self.directories)
            mode, args = self.request
            rows = (
                client.latest(*args, cancelled=self.isInterruptionRequested)
                if mode == "latest"
                else client.directory(args)
            )
            if not self.isInterruptionRequested():
                self.result.emit(rows, client.directories, client.files)
        except Exception as exc:
            if not self.isInterruptionRequested():
                self.failed.emit(str(exc))
        finally:
            if client is not None:
                client.close()


class FileDownload(QThread):
    result = Signal(object)
    progress = Signal(object, object)
    failed = Signal(str)

    def __init__(self, connection, files, path, target, parent=None):
        super().__init__(parent)
        self.connection, self.files = connection, dict(files)
        self.path, self.target = path, target

    def run(self):
        client = None
        try:
            client = DeviceFilesClient(**self.connection)
            client.files.update(self.files)
            result = client.download(
                self.path,
                self.target,
                cancelled=self.isInterruptionRequested,
                progress=self.progress.emit,
            )
            self.result.emit(result)
        except Exception as exc:
            if not self.isInterruptionRequested():
                self.failed.emit(str(exc))
        finally:
            if client is not None:
                client.close()


class DeviceFilesPage(QWidget):
    idle = Signal()

    def __init__(self):
        super().__init__()
        self.connection = None
        self.query = None
        self.generation = 0
        self.directories = {DATA}
        self.files = {}
        self.current_directory = DATA
        self.rows = []
        self.offset = 0
        layout = QVBoxLayout(self)
        note = QLabel(
            "Saved files in SLM internal memory. Load explicitly; nothing opens or changes the measurement on the instrument. Dates use the SLM clock. Select a directory and Browse selected to see its saved files. Download advertised files unchanged to your PC. Native BKC decoding is not yet supported; downloading never opens a measurement on the SLM."
        )
        note.setWordWrap(True)
        layout.addWidget(note)
        controls = QGridLayout()
        self.limit = QSpinBox()
        self.limit.setRange(1, 999)
        self.limit.setValue(100)
        self.dates = QCheckBox("Between dates (inclusive)")
        self.start_date = QDateEdit(QDate.currentDate().addDays(-30))
        self.end_date = QDateEdit(QDate.currentDate())
        for field in (self.start_date, self.end_date):
            field.setCalendarPopup(True)
            field.setDisplayFormat("yyyy-MM-dd")
        controls.addWidget(QLabel("Last measurement records"), 0, 0)
        controls.addWidget(self.limit, 0, 1)
        controls.addWidget(self.dates, 1, 0)
        controls.addWidget(self.start_date, 1, 1)
        controls.addWidget(self.end_date, 1, 2)
        self.load = QPushButton("Load latest records")
        self.all = QPushButton("Browse all folders")
        self.open = QPushButton("Browse selected directory")
        self.download = QPushButton("Download selected file…")
        self.download.clicked.connect(self.download_selected)
        self.up = QPushButton("Parent folder")
        self.up.clicked.connect(self.parent_directory)
        self.cancel = QPushButton("Cancel")
        for column, button in enumerate(
            (self.load, self.all, self.open, self.up, self.download, self.cancel)
        ):
            controls.addWidget(button, 2 + column // 2, column % 2, 1, 1)
        self.load.clicked.connect(self.load_latest)
        self.all.clicked.connect(lambda: self.fetch("directory", DATA))
        self.open.clicked.connect(self.open_selected)
        self.cancel.clicked.connect(self.stop)
        layout.addLayout(controls)
        self.status = QLabel("Connect to an SLM first. No files are loaded automatically.")
        self.status.setWordWrap(True)
        self.status.setTextFormat(Qt.TextFormat.PlainText)
        self.status.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.breadcrumb = QLabel("SLM / Data")
        self.breadcrumb.setWordWrap(True)
        self.breadcrumb.setTextFormat(Qt.TextFormat.PlainText)
        layout.addWidget(self.breadcrumb)
        layout.addWidget(self.status)
        self.table = QTableWidget(0, 3)
        self.table.setHorizontalHeaderLabels(["Saved record / file", "Type", "Instrument path"])
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.itemSelectionChanged.connect(self.update_buttons)
        layout.addWidget(self.table, 1)
        pages = QGridLayout()
        self.previous = QPushButton("Previous 100")
        self.next = QPushButton("Next 100")
        self.previous.clicked.connect(lambda: self.change_page(-100))
        self.next.clicked.connect(lambda: self.change_page(100))
        pages.addWidget(self.previous, 0, 0)
        pages.addWidget(self.next, 0, 1)
        layout.addLayout(pages)
        self.update_buttons()

    def set_connection(self, connection):
        self.generation += 1
        self.stop()
        self.connection = dict(connection) if connection else None
        self.directories = {DATA}
        self.files = {}
        self.current_directory = DATA
        self.rows = []
        self.offset = 0
        self.table.setRowCount(0)
        self.breadcrumb.setText("SLM / Data")
        self.status.setText(
            "Connected. Choose Load latest records or Browse all folders."
            if connection
            else "Disconnected. Connect to an SLM to browse saved files."
        )
        self.update_buttons()

    def stop(self):
        if self.query:
            self.query.requestInterruption()
            self.status.setText("Cancelling the current read…")

    def load_latest(self):
        start = self.start_date.date().toPython() if self.dates.isChecked() else None
        end = self.end_date.date().toPython() if self.dates.isChecked() else None
        if start and start > end:
            self.status.setText("Start date must be on or before end date.")
            return
        self.fetch("latest", (self.limit.value(), start, end))

    def open_selected(self):
        index = self.offset + self.table.currentRow()
        if self.table.currentRow() < 0 or index >= len(self.rows):
            self.status.setText("Select a directory first.")
            return
        _, kind, path = self.rows[index]
        if kind != "Directory":
            self.status.setText(
                "Select Download selected file to preserve its original bytes. No instrument Open action is sent."
            )
            return
        self.fetch("directory", path)

    def parent_directory(self):
        if self.current_directory and self.current_directory != DATA:
            parent = self.current_directory.rsplit("/", 1)[0]
            if parent in self.directories:
                self.fetch("directory", parent)

    def download_selected(self):
        row = self.table.currentRow()
        index = self.offset + row
        if self.query or not self.connection or row < 0 or index >= len(self.rows):
            return
        name, kind, path = self.rows[index]
        if kind != "File" or path not in self.files:
            return
        # The user chooses the local destination; never use a remote path as a local path.
        safe_name = (
            "".join(c if c.isalnum() or c in ".-_" else "_" for c in name).strip(".")
            or "measurement.bkc"
        )
        target, _ = QFileDialog.getSaveFileName(
            self, "Save original instrument file (new filename)", safe_name, "All files (*)"
        )
        if not target:
            return
        generation = self.generation
        self.query = FileDownload(self.connection, self.files, path, Path(target), self)
        self.query.progress.connect(
            lambda size, total: (
                self.status.setText(
                    f"Downloading {size:,}"
                    + (f" / {total:,}" if total is not None else "")
                    + " bytes…"
                )
                if generation == self.generation
                else None
            )
        )
        self.query.result.connect(
            lambda result: (
                self.status.setText(
                    f"Saved original file: {result['path']}\n{result['bytes']:,} bytes · SHA-256: {result['sha256']}\nBKC analysis is not implemented; keep this original for later analysis."
                )
                if generation == self.generation
                else None
            )
        )
        self.query.failed.connect(
            lambda message: self.status.setText(message) if generation == self.generation else None
        )
        self.query.finished.connect(self.finished)
        self.update_buttons()
        self.query.start()

    def fetch(self, mode, args):
        if not self.connection or self.query:
            return
        self.rows = []
        self.offset = 0
        self.table.setRowCount(0)
        self.current_directory = args if mode == "directory" else None
        self.breadcrumb.setText(
            unquote(args.removeprefix(DATA)) or "SLM / Data"
            if mode == "directory"
            else "Latest records (date-filtered inventory)"
        )
        generation = self.generation
        self.query = FileQuery(self.connection, self.directories, (mode, args), self)
        self.query.result.connect(
            lambda rows, directories, files: self.loaded(generation, rows, directories, files)
        )
        self.query.failed.connect(
            lambda message: self.status.setText(message) if generation == self.generation else None
        )
        self.query.finished.connect(self.finished)
        self.status.setText("Reading saved inventory from the SLM…")
        self.update_buttons()
        self.query.start()

    def loaded(self, generation, rows, directories, files):
        if generation != self.generation:
            return
        self.rows = rows
        self.directories = directories
        self.files = files
        self.change_page(0)

    def change_page(self, step):
        self.offset = max(0, min(self.offset + step, max(0, ((len(self.rows) - 1) // 100) * 100)))
        visible = self.rows[self.offset : self.offset + 100]
        self.table.setRowCount(len(visible))
        for row, values in enumerate(visible):
            for column, value in enumerate(values):
                item = QTableWidgetItem(value)
                if values[2] in self.files:
                    item.setToolTip(
                        "Advertised file metadata: "
                        + str(self.files[values[2]].get("metadata", {}))
                    )
                self.table.setItem(row, column, item)
        self.table.setColumnWidth(0, 330)
        self.status.setText(
            f"{len(self.rows)} entries in this result; showing {self.offset + 1 if visible else 0}–{self.offset + len(visible)}. Latest results respect your record limit; Browse all traverses one directory at a time."
        )
        self.update_buttons()

    def finished(self):
        cancelled = self.query.isInterruptionRequested()
        self.query.deleteLater()
        self.query = None
        if cancelled and self.connection:
            self.status.setText("Read cancelled. Choose a load button to try again.")
        self.update_buttons()
        self.idle.emit()

    def update_buttons(self):
        ready = bool(self.connection) and self.query is None
        for button in (self.load, self.all, self.open):
            button.setEnabled(ready)
        row = self.table.currentRow()
        index = self.offset + row
        selected = self.rows[index] if row >= 0 and index < len(self.rows) else None
        self.download.setEnabled(
            ready and selected is not None and selected[1] == "File" and selected[2] in self.files
        )
        self.up.setEnabled(ready and self.current_directory not in (None, DATA))
        self.cancel.setEnabled(self.query is not None)
        self.previous.setEnabled(ready and self.offset > 0)
        self.next.setEnabled(ready and self.offset + 100 < len(self.rows))
