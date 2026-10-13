"""Desktop alpha: explicit data origin, responsive controls, bounded visual history."""

import hashlib
import json
from collections import deque
from datetime import datetime
from pathlib import Path
from time import monotonic

import pyqtgraph as pg
from PySide6.QtCore import QSettings, QStandardPaths, Qt, QThread, QTimer, Signal
from PySide6.QtGui import QAction, QCloseEvent, QColor, QPalette
from PySide6.QtNetwork import QAbstractSocket, QNetworkInterface
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QMainWindow,
    QMenu,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QStackedWidget,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)

from bnkg import FULL_NAME, __version__
from bnkg.core.device import DEMO_MODES
from bnkg.core.export_profiles import RAW, SPECTRAL, describe, profile
from bnkg.core.parameters import DEFAULT_VISIBLE, PARAMETERS, Sample
from bnkg.core.report_context import log_filename
from bnkg.core.spectrum import finite
from bnkg.core.trends import TrendPoint
from bnkg.ui.about import AboutPage, construction_banner
from bnkg.ui.audio import AudioPanel
from bnkg.ui.bkc import BkcPanel
from bnkg.ui.charts import TrendChart
from bnkg.ui.components import AppearanceSelector, ArmControlsCheckBox, ScreenPane
from bnkg.ui.device_files import DeviceFilesPage
from bnkg.ui.diagnostics import ConnectionDiagnostics
from bnkg.ui.discovery import DiscoveryThread
from bnkg.ui.export_profiles import ExportPresets
from bnkg.ui.exporting import ExportJob
from bnkg.ui.guidance import WorkflowHelp
from bnkg.ui.history import HistoryBrowser
from bnkg.ui.live_views import DemoPage, FrequencyPage, MetadataPage
from bnkg.ui.media import MediaPanel
from bnkg.ui.parameters import ParameterCatalogue
from bnkg.ui.preferences import PreferencesDialog
from bnkg.ui.presentation import LevelBar, Page, ParameterTile, SpectrumPreview
from bnkg.ui.recording import RecordingPanel
from bnkg.ui.worker import AcquisitionWorker

DISCLAIMER = (
    "Independent application by Gadash (Akila DJ). Not affiliated with, endorsed by, "
    "sponsored by, or supported by Hottinger Brüel & Kjær. HBK, Brüel & Kjær and B&K "
    "are trademarks of their respective owners. This app is under construction. "
    "Some information may be incomplete, delayed or displayed incorrectly. "
    "Double-check readings, units and settings on the instrument and against its "
    "official documentation before relying on them."
)


class MainWindow(QMainWindow):
    command_requested = Signal(str, object)
    shutdown_requested = Signal()

    def __init__(self, *, data_dir: Path | None = None, demo: bool = False) -> None:
        super().__init__()
        self.setWindowTitle(FULL_NAME)
        self.resize(1280, 880)
        self.setMinimumSize(440, 660)
        self.data_dir = data_dir or Path(
            QStandardPaths.writableLocation(QStandardPaths.StandardLocation.AppLocalDataLocation)
        )
        legacy_data = self.data_dir.parent / "HBKG"
        if data_dir is None and not self.data_dir.exists() and legacy_data.is_dir():
            self.data_dir = legacy_data
        self.settings = QSettings(
            str(self.data_dir / "preferences.ini"), QSettings.Format.IniFormat
        )
        self.pending_connection = {}
        self.capturing = False
        self.discovery = None
        self.worker_done = False
        self.logging = False
        self.source_mode = "disconnected"
        self.session_path = ""
        self.export_job = None
        self.export_parameters = [p.id for p in PARAMETERS]
        self.closing = False
        self.thread_finished = False
        self.last_received = None
        self.latest: Sample | None = None
        self.history: deque[tuple[float, float]] = deque(maxlen=100)
        self.tiles: dict[str, ParameterTile] = {}
        self.checks: dict[str, QCheckBox] = {}
        self._build()
        self.thread = QThread(self)
        self.worker = AcquisitionWorker(audit_dir=self.data_dir / "audit")
        self.worker.moveToThread(self.thread)
        self.thread.started.connect(self.worker.start)
        self.command_requested.connect(self.worker.command)
        self.shutdown_requested.connect(self.worker.shutdown)
        self.worker.sample.connect(self.receive_sample)
        self.worker.location_previewed.connect(self.metadata_page.location.confirm_preview)
        self.worker.location_written.connect(self.metadata_page.location.written)
        self.worker.captured.connect(self.receive_captured)
        self.worker.capture_changed.connect(self.receive_capture)
        self.worker.screen.connect(self.slm_screen.set_image)
        self.worker.recording_frame.connect(
            self.recording_panel.submit, Qt.ConnectionType.DirectConnection
        )
        self.recording_panel.polling.connect(
            lambda active: self.command_requested.emit("record_screen", active)
        )
        self.recording_panel.idle.connect(self.files_idle)
        self.recording_panel.activity.connect(self.show_recording_status)
        self.recording_panel.idle.connect(self.recording_notice.hide)
        self.worker.screen_status.connect(self.slm_screen.set_status)
        self.worker.controls.connect(self.receive_controls)
        self.worker.keypad_state.connect(self.receive_keypad_state)
        self.worker.connected.connect(self.remember_connection)
        self.worker.status.connect(self.receive_status)
        self.worker.session_changed.connect(self.receive_session)
        self.worker.failure.connect(self.show_error)
        self.worker.finished.connect(self.thread.quit)
        self.worker.finished.connect(self.worker.deleteLater)
        self.thread.finished.connect(self.worker_closed)
        self.thread.start()
        self.apply_display_preferences()
        self.freshness_timer = QTimer(self)
        self.freshness_timer.setInterval(1000)
        self.freshness_timer.timeout.connect(self.update_freshness)
        self.freshness_timer.start()
        self.apply_theme(self.settings.value("theme", "Dark"))
        QApplication.styleHints().colorSchemeChanged.connect(
            lambda _: self.apply_theme(self.theme.currentText())
        )
        geometry = self.settings.value("geometry")
        if geometry:
            self.restoreGeometry(geometry)
        if demo:
            QTimer.singleShot(50, lambda: self.select_source("demo"))

    def _build(self) -> None:
        root = QWidget()
        outer = QHBoxLayout(root)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)
        sidebar = self.sidebar = QFrame()
        sidebar.setObjectName("sidebar")
        sidebar.setFixedWidth(190)
        side = QVBoxLayout(sidebar)
        side.setContentsMargins(22, 24, 18, 20)
        brand = QLabel("B&KG")
        brand.setObjectName("brand")
        side.addWidget(brand)
        subtitle = QLabel("SLM REMOTE STUDIO\nby Gadash")
        subtitle.setObjectName("muted")
        side.addWidget(subtitle)
        side.addSpacing(28)
        self.navigation = QListWidget()
        self.navigation.setObjectName("navigation")
        self.navigation.addItems(
            [
                "Dashboard",
                "SLM screen",
                "Parameters",
                "Data table",
                "Sessions & export",
                "Connection",
                "Device files",
                "Help & About",
                "Frequency Analysis",
                "Metadata",
                "Demo Lab",
            ]
        )
        side.addWidget(self.navigation)
        for note in (f"{__version__} · Development alpha", "Local storage · No telemetry"):
            label = QLabel(note)
            label.setWordWrap(True)
            side.addWidget(label)
        outer.addWidget(sidebar)
        main = self.main_layout = QVBoxLayout()
        main.setContentsMargins(28, 22, 28, 16)
        main.setSpacing(14)
        header = QVBoxLayout()
        self.mobile_navigation = QComboBox()
        self.mobile_navigation.addItems(
            [self.navigation.item(i).text() for i in range(self.navigation.count())]
        )
        self.mobile_navigation.currentIndexChanged.connect(self.navigation.setCurrentRow)
        self.navigation.currentRowChanged.connect(self.mobile_navigation.setCurrentIndex)
        main.addWidget(self.mobile_navigation)
        self.mobile_navigation.hide()
        title = QLabel(FULL_NAME)
        title.setWordWrap(True)
        title.setTextFormat(Qt.TextFormat.PlainText)
        title.setObjectName("heading")
        header.addWidget(title)
        appearance = QHBoxLayout()
        self.about_button = QPushButton("About")
        self.about_button.clicked.connect(lambda: self.navigation.setCurrentRow(Page.ABOUT))
        appearance.addWidget(self.about_button)
        self.navigation.item(Page.ABOUT).setHidden(True)
        self.mobile_navigation.view().setRowHidden(Page.ABOUT, True)
        self.theme = AppearanceSelector()
        self.theme.setAccessibleName("Appearance theme")
        self.theme.currentTextChanged.connect(self.apply_theme)
        appearance.addWidget(self.theme)
        self.color_theme = QComboBox()
        self.color_theme.addItems(["B&KG", "Colorful", "Blue", "Red", "Green"])
        self.color_theme.setCurrentText(self.settings.value("color_theme", "B&KG"))
        self.color_theme.setAccessibleName("Color theme")
        self.color_theme.currentTextChanged.connect(
            lambda _: self.apply_theme(self.theme.currentText())
        )
        appearance.addWidget(self.color_theme)
        self.preferences_button = QPushButton("Display…")
        self.preferences_button.setAccessibleName("Display preferences")
        self.preferences_button.setToolTip("Display preferences")
        self.preferences_button.clicked.connect(self.open_preferences)
        appearance.addWidget(self.preferences_button)
        appearance.addStretch()
        header.addLayout(appearance)
        main.addLayout(header)
        main.addWidget(construction_banner())
        self.origin_banner = QLabel(
            "NOT CONNECTED  ·  Enter or find the instrument address in Connection"
        )
        self.origin_banner.setObjectName("banner")
        self.origin_banner.setWordWrap(True)
        main.addWidget(self.origin_banner)
        self.recording_notice = QLabel()
        self.recording_notice.setWordWrap(True)
        self.recording_notice.setObjectName("banner")
        self.recording_notice.hide()
        main.addWidget(self.recording_notice)
        controls = self.local_controls = QGridLayout()
        self.demo_button = QPushButton("Start demo")
        self.demo_button.clicked.connect(self.toggle_demo)
        self.demo_mode = QComboBox()
        self.demo_mode.addItems(DEMO_MODES)
        self.demo_mode.setAccessibleName("Demo scenario")
        self.demo_mode.setToolTip(
            "Smooth sine / varying ambient noise / intermittent events. All synthetic."
        )
        self.pause_button = QPushButton("Pause demo")
        self.pause_button.setEnabled(False)
        self.pause_button.clicked.connect(self.pause_demo)
        self.local_capture_button = QPushButton("Start local capture")
        self.local_capture_button.setEnabled(False)
        self.local_capture_button.clicked.connect(
            lambda: self.command_requested.emit(
                "capture_stop" if self.capturing else "capture_start", None
            )
        )
        self.log_button = QPushButton("Start file logging")
        self.log_button.setEnabled(False)
        self.log_button.clicked.connect(self.toggle_logging)
        self.capture_button = QPushButton("Screenshot")
        self.capture_button.clicked.connect(self.screenshot)
        self.demo_button.hide()
        self.demo_mode.hide()
        self.pause_button.hide()
        self.local_widgets = [
            self.local_capture_button,
            self.log_button,
            self.capture_button,
        ]
        for i, widget in enumerate(self.local_widgets):
            controls.addWidget(widget, i // 3, i % 3)
        # Local controls belong to Data table, away from the main live header.
        self.local_status = QLabel("LIVE VIEW ONLY · Local capture off · No log file open")
        self.local_status.setWordWrap(True)
        self.local_status.setObjectName("muted")
        # Status accompanies local controls in Data table.
        self.pages = QStackedWidget()
        self.pages.addWidget(self.build_dashboard())
        self.pages.addWidget(self.build_slm_screen())
        self.pages.addWidget(self.build_parameters())
        self.pages.addWidget(self.build_table())
        self.pages.addWidget(self.build_sessions())
        self.pages.addWidget(self.build_connection())
        self.device_files = DeviceFilesPage()
        self.device_files.idle.connect(self.files_idle)
        self.pages.addWidget(self.device_files)
        self.pages.addWidget(self.build_help())
        self.frequency_page = FrequencyPage(self.settings)
        self.pages.addWidget(self.frequency_page)
        self.metadata_page = MetadataPage(self.settings)
        self.metadata_page.selected_changed.connect(self.metadata_summary.setText)
        self.metadata_page.location.command.connect(self.command_requested.emit)
        metadata_scroll = QScrollArea()
        metadata_scroll.setWidgetResizable(True)
        metadata_scroll.setWidget(self.metadata_page)
        self.pages.addWidget(metadata_scroll)
        self.demo_page = DemoPage(self.settings)
        self.frequency_page.palette_changed.connect(
            lambda: self.apply_theme(self.theme.currentText())
        )
        self.demo_page.frequency.palette_changed.connect(
            lambda: self.apply_theme(self.theme.currentText())
        )
        demo_scroll = QScrollArea()
        demo_scroll.setWidgetResizable(True)
        demo_scroll.setWidget(self.demo_page)
        self.pages.addWidget(demo_scroll)
        self.navigation.currentRowChanged.connect(self.pages.setCurrentIndex)
        self.navigation.currentRowChanged.connect(
            lambda index: self.command_requested.emit("screen", index == Page.SLM)
        )
        self.navigation.setCurrentRow(Page.DASHBOARD)
        main.addWidget(self.pages, 1)
        self.footer = QLabel("Ready. No device requests run automatically.")
        self.footer.setWordWrap(True)
        self.footer.setObjectName("muted")
        main.addWidget(self.footer)
        outer.addLayout(main, 1)
        self.setCentralWidget(root)
        fullscreen = QAction("Fullscreen", self)
        fullscreen.setShortcut("F11")
        fullscreen.triggered.connect(
            lambda: self.showNormal() if self.isFullScreen() else self.showFullScreen()
        )
        self.addAction(fullscreen)

    def build_dashboard(self) -> QWidget:
        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(0, 0, 4, 0)
        self.dashboard_status = QLabel("SLM · no fresh sample")
        self.dashboard_status.setWordWrap(True)
        layout.addWidget(self.dashboard_status)
        self.level_bar = LevelBar()
        layout.addWidget(self.level_bar)
        self.metric_grid = QGridLayout()
        self.metric_grid.setSpacing(12)
        for parameter in PARAMETERS:
            self.tiles[parameter.id] = ParameterTile(
                parameter.label, parameter.description, bool(parameter.formula)
            )
        layout.addWidget(QLabel("SLM OUTPUTS · Each tile identifies its measurement scope"))
        layout.addLayout(self.metric_grid)
        self.spectrum_preview = SpectrumPreview()
        layout.addWidget(self.spectrum_preview)
        self.frequency_shortcut = QPushButton("Open Frequency Analysis")
        self.frequency_shortcut.clicked.connect(
            lambda: self.navigation.setCurrentRow(Page.FREQUENCY)
        )
        layout.addWidget(self.frequency_shortcut)
        self.metadata_summary = QLabel("Select fields in Metadata to show them here.")
        self.metadata_summary.setWordWrap(True)
        layout.addWidget(self.metadata_summary)
        self.local_calculations = QLabel("Local calculation · LCeq − LAeq: unavailable")
        self.local_calculations.setWordWrap(True)
        layout.addWidget(self.local_calculations)
        trend_heading = QLabel("LAF / LOCAL CAPTURE · bounded recent history")
        trend_heading.setObjectName("subheading")
        layout.addWidget(trend_heading)
        self.plot = pg.PlotWidget()
        self.plot.setMinimumHeight(200)
        self.plot.setLabel("left", "LAF", units="dB")
        self.plot.setLabel("bottom", "PC receipt time", units="s")
        self.plot.showGrid(x=True, y=True, alpha=0.15)
        self.curve = self.plot.plot(pen=pg.mkPen("#45b7ff", width=2))
        layout.addWidget(self.plot)
        layout.addStretch()
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(content)
        self.arrange_tiles(DEFAULT_VISIBLE)
        return scroll

    def open_preferences(self):
        dialog = PreferencesDialog(self.settings, self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            dialog.save(self.settings)
            self.apply_display_preferences()
            self.apply_theme(self.theme.currentText())

    def apply_display_preferences(self):
        compact = self.settings.value("tile_density", "Comfortable") == "Compact"
        for tile in list(self.tiles.values()) + list(self.demo_page.tiles.values()):
            tile.setMinimumHeight(92 if compact else 132)
            tile.layout().setSpacing(2 if compact else 6)
        self.metric_grid.setSpacing(8 if compact else 12)
        self.level_bar.setVisible(self.settings.value("dashboard_meter", True, type=bool))
        preview = self.settings.value("dashboard_spectrum", False, type=bool)
        self.spectrum_preview.setVisible(preview)
        self.frequency_shortcut.setVisible(preview)
        self.frequency_page.range.setCurrentText(
            self.settings.value("spectrum_range", "Auto range")
        )
        self.level_bar.update_level(
            self.latest.values.get("LAF")
            if self.latest and self.last_received is not None
            else None,
            self.settings.value("dashboard_range", "20–140 dB") == "20–140 dB",
        )

    def update_freshness(self):
        self.connection_diagnostics.refresh()
        if self.last_received is None or self.latest is None:
            return
        age = max(0, monotonic() - self.last_received)
        self.dashboard_status.setText(
            f"SLM · {self.latest.state} · received {age:.0f} s ago · {self.latest.timestamp.astimezone():%H:%M:%S %Z}\n{self.latest.quality}"
        )

    def build_parameters(self) -> QWidget:
        selected = self.settings.value("visible", list(DEFAULT_VISIBLE))
        # Migrate the previous default, which hid the only currently acquired live metric.
        old_default = [parameter.id for parameter in PARAMETERS[:9]]
        if selected == old_default and not self.settings.value(
            "laf_default_migrated", False, type=bool
        ):
            selected = list(DEFAULT_VISIBLE)
        self.settings.setValue("laf_default_migrated", True)
        self.parameter_catalogue = ParameterCatalogue(self.settings, selected)
        self.checks = self.parameter_catalogue.checks
        self.parameter_catalogue.selection_changed.connect(self.update_visible)
        self.update_visible()
        return self.parameter_catalogue

    def arrange_tiles(self, selected) -> None:
        while self.metric_grid.count():
            self.metric_grid.takeAt(0)
        for tile in self.tiles.values():
            tile.hide()
        for index, key in enumerate(selected):
            if key in self.tiles and not next(p for p in PARAMETERS if p.id == key).formula:
                tile = self.tiles[key]
                tile.show()
                columns = 1 if self.width() < 600 else (2 if self.width() < 1000 else 3)
                self.metric_grid.addWidget(tile, index // columns, index % columns)
        for column in range(3):
            columns = 1 if self.width() < 600 else (2 if self.width() < 1000 else 3)
            self.metric_grid.setColumnStretch(column, 1 if column < columns else 0)

    def update_visible(self) -> None:
        selected = [key for key, check in self.checks.items() if check.isChecked()]
        selected.sort(key=lambda key: key != "LAF")
        self.arrange_tiles(selected)
        self.settings.setValue("visible", selected)

    def build_table(self) -> QWidget:
        self.extra_columns = [p for p in PARAMETERS if p.id not in {"LAF", "LAeq"}]
        self.table = QTableWidget(0, 6 + len(self.extra_columns))
        self.table.setHorizontalHeaderLabels(
            ["PC time (UTC)", "Elapsed s", "LAF dB", "LAeq dB", "State", "Origin"]
            + [p.label + (" · Calculated" if p.formula else "") + " dB" for p in self.extra_columns]
        )
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.setColumnWidth(0, 225)
        for column, parameter in [
            (2, next(p for p in PARAMETERS if p.id == "LAF")),
            (3, next(p for p in PARAMETERS if p.id == "LAeq")),
        ] + list(enumerate(self.extra_columns, 6)):
            self.table.horizontalHeaderItem(column).setToolTip(parameter.description)
        self.table.setToolTip(
            "Only locally captured records. Set the memory limit above; export the file for full logged history."
        )
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.addLayout(self.local_controls)
        layout.addWidget(self.local_status)
        options = QHBoxLayout()
        options.addWidget(QLabel("Newest records in memory:"))
        self.record_limit = QSpinBox()
        self.record_limit.setRange(1, 999)
        self.record_limit.setValue(int(self.settings.value("record_limit", 100)))
        self.record_limit.valueChanged.connect(self.set_record_limit)
        options.addWidget(self.record_limit)
        options.addStretch()
        layout.addLayout(options)
        view_controls = QHBoxLayout()
        self.auto_scroll = QCheckBox("Auto-scroll")
        self.auto_scroll.setChecked(True)
        view_controls.addWidget(self.auto_scroll)
        columns_button = QPushButton("Columns…")
        menu = QMenu(columns_button)
        defaults = [str(i) for i in range(6)]
        visible = self.settings.value("capture_columns", defaults)
        for i in range(self.table.columnCount()):
            action = menu.addAction(self.table.horizontalHeaderItem(i).text())
            action.setCheckable(True)
            action.setChecked(str(i) in visible)
            self.table.setColumnHidden(i, not action.isChecked())
            action.toggled.connect(
                lambda checked, column=i: self.set_capture_column(column, checked)
            )
        columns_button.setMenu(menu)
        view_controls.addWidget(columns_button)
        self.clear_view_button = QPushButton("Clear view only")
        self.clear_view_button.clicked.connect(self.clear_capture_view)
        view_controls.addWidget(self.clear_view_button)
        layout.addLayout(view_controls)
        info = QLabel(
            "Local capture adds rows. File logging preserves the full session, even when older rows leave this view."
        )
        info.setWordWrap(True)
        layout.addWidget(info)
        self.capture_chart = TrendChart()
        self.capture_tabs = QTabWidget()
        self.capture_tabs.addTab(self.table, "Table")
        self.capture_tabs.addTab(self.capture_chart, "Charts")
        layout.addWidget(self.capture_tabs, 1)
        self.set_record_limit(self.record_limit.value())
        return page

    def set_capture_column(self, column, visible):
        self.table.setColumnHidden(column, not visible)
        self.settings.setValue(
            "capture_columns",
            [str(i) for i in range(self.table.columnCount()) if not self.table.isColumnHidden(i)],
        )

    def clear_capture_view(self):
        self.table.setRowCount(0)
        self.history.clear()
        self.curve.setData([], [])
        self.capture_chart.set_points([])

    def build_sessions(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        heading = QLabel("Local sessions & export")
        heading.setObjectName("heading")
        layout.addWidget(heading)
        self.session_info = QLabel(
            "No session selected. Start local logging to create a SQLite session."
        )
        self.session_info.setWordWrap(True)
        self.session_info.setTextFormat(Qt.TextFormat.PlainText)
        self.session_info.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        layout.addWidget(self.session_info)
        open_button = self.export_open_button = QPushButton("Open existing session for export…")
        open_button.clicked.connect(self.open_session)
        layout.addWidget(open_button)
        self.format_box = QComboBox()
        self.format_box.addItems(["CSV", "XLSX", "TSV", "TXT", "JSON", "NDJSON", "HTML"])
        layout.addWidget(self.format_box)
        parameter_button = self.export_parameter_button = QPushButton("Choose exported parameters…")
        parameter_button.clicked.connect(self.choose_export_parameters)
        layout.addWidget(parameter_button)
        self.export_spectra = QCheckBox("Include supported direct spectra and descriptors")
        self.export_raw = QCheckBox("Include stored raw outputs/context (JSON / NDJSON)")
        self.export_raw.setChecked(True)
        layout.addWidget(self.export_spectra)
        layout.addWidget(self.export_raw)
        self.format_box.currentTextChanged.connect(self.update_export_options)
        self.export_preview = QTextBrowser()
        self.export_preview.setMinimumHeight(200)
        self.export_preview.setMaximumHeight(320)
        self.export_preview.setAccessibleName("Export content preview")
        layout.addWidget(self.export_preview)
        self.export_spectra.toggled.connect(self.refresh_export_preview)
        self.export_raw.toggled.connect(self.refresh_export_preview)
        self.export_presets = ExportPresets(self.settings, self.current_export_profile)
        self.export_presets.apply_requested.connect(self.apply_export_profile)
        presets_button = QPushButton("Show export presets")
        presets_button.setCheckable(True)
        presets_button.toggled.connect(self.export_presets.setVisible)
        presets_button.toggled.connect(
            lambda shown: presets_button.setText(
                "Hide export presets" if shown else "Show export presets"
            )
        )
        layout.addWidget(presets_button)
        layout.addWidget(self.export_presets)
        self.export_presets.hide()
        self.update_export_options()
        self.export_status = QLabel("Choose a new export filename. The source log is unchanged.")
        self.export_status.setTextFormat(Qt.TextFormat.PlainText)
        self.export_status.setWordWrap(True)
        layout.addWidget(self.export_status)
        self.export_progress = QProgressBar()
        self.export_progress.setRange(0, 100)
        self.export_progress.setValue(0)
        layout.addWidget(self.export_progress)
        self.cancel_export_button = QPushButton("Cancel export")
        self.cancel_export_button.setEnabled(False)
        self.cancel_export_button.clicked.connect(self.cancel_export)
        layout.addWidget(self.cancel_export_button)
        self.export_button = QPushButton("Export selected session…")
        self.export_button.clicked.connect(self.export_current)
        layout.addWidget(self.export_button)
        note = QLabel(
            "Exports preserve data origin and quality. JSON/XLSX include parameter metadata.\nTXT is tab-separated. No existing export is overwritten.\n\nExports run independently; monitoring and logging continue. A consistent snapshot excludes later rows. Cancel is checked between rows; XLSX packaging may need to finish before cleanup."
        )
        note.setWordWrap(True)
        layout.addWidget(note)
        layout.addStretch()
        self.session_tabs = QTabWidget()
        self.history_browser = HistoryBrowser(self.data_dir / "sessions")
        self.history_browser.idle.connect(self.files_idle)
        self.history_browser.spectrum_selected.connect(self.load_saved_spectrum)
        self.session_tabs.addTab(self.history_browser, "Browse history")
        self.bkc_panel = BkcPanel(self.data_dir)
        self.bkc_panel.idle.connect(self.files_idle)
        self.bkc_panel.spectrum_selected.connect(self.load_saved_spectrum)
        self.session_tabs.addTab(self.bkc_panel, "Native BKC")
        export_scroll = QScrollArea()
        export_scroll.setWidgetResizable(True)
        export_scroll.setWidget(page)
        self.session_tabs.addTab(export_scroll, "Export")
        return self.session_tabs

    def current_export_profile(self, format_name=None):
        return profile(
            format_name or self.format_box.currentText().lower(),
            self.export_parameters,
            self.export_spectra.isChecked(),
            self.export_raw.isChecked(),
        )

    def update_export_options(self):
        name = self.format_box.currentText().lower()
        ready = self.export_job is None
        self.export_spectra.setEnabled(ready and name in SPECTRAL)
        self.export_raw.setEnabled(ready and name in RAW)
        if hasattr(self, "export_preview"):
            self.refresh_export_preview()

    def refresh_export_preview(self, *_):
        if not hasattr(self, "export_preview"):
            return
        try:
            if self.export_job is not None:
                job = self.export_job
                value = profile(
                    job.format_name,
                    job.options["parameter_ids"],
                    job.options["include_spectra"],
                    job.options["include_raw"],
                )
                heading = f"RUNNING EXPORT · Options captured at start\nSource: {job.database}\nDestination: {job.target}\n\n"
            else:
                value = self.current_export_profile()
                heading = (
                    "CURRENT EXPORT OPTIONS\nSource: "
                    + (self.session_path or "no session selected")
                    + "\n\n"
                )
            content = heading + describe(value)
            if self.export_preview.toPlainText() != content:
                self.export_preview.setPlainText(content)
        except ValueError as exc:
            self.export_preview.setPlainText("Export not ready: " + str(exc))

    def apply_export_profile(self, value):
        if self.export_job is not None:
            return
        self.export_parameters = list(value.parameter_ids)
        for widget in (self.format_box, self.export_spectra, self.export_raw):
            widget.blockSignals(True)
        self.format_box.setCurrentText(value.format_name.upper())
        self.export_spectra.setChecked(value.include_spectra)
        self.export_raw.setChecked(value.include_raw)
        for widget in (self.format_box, self.export_spectra, self.export_raw):
            widget.blockSignals(False)
        self.update_export_options()

    def set_export_busy(self, busy):
        for widget in (
            self.format_box,
            self.export_parameter_button,
            self.export_presets,
            self.export_open_button,
        ):
            widget.setEnabled(not busy)
        self.update_export_options()

    def choose_export_parameters(self):
        if self.export_job is not None:
            return
        dialog = QDialog(self)
        dialog.setWindowTitle("Exported parameters")
        layout = QVBoxLayout(dialog)
        content = QWidget()
        choices = QVBoxLayout(content)
        checks = []
        for parameter in PARAMETERS:
            check = QCheckBox(parameter.label + (" · Calculated" if parameter.formula else ""))
            check.setToolTip(parameter.description)
            check.setChecked(parameter.id in self.export_parameters)
            choices.addWidget(check)
            checks.append((parameter.id, check))
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(content)
        layout.addWidget(scroll)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)
        dialog.resize(430, 580)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.export_parameters = [key for key, check in checks if check.isChecked()]
            self.refresh_export_preview()

    def load_saved_spectrum(self, frame, label):
        self.frequency_page.load_saved(frame, label)
        self.navigation.setCurrentRow(Page.FREQUENCY)

    def build_slm_screen(self):
        panel = QFrame()
        panel.setObjectName("controlPanel")
        layout = QVBoxLayout(panel)
        title = QLabel("SLM / MEASUREMENT")
        title.setObjectName("subheading")
        layout.addWidget(title)
        note = QLabel(
            "These controls change the instrument. Local capture and file logging are independent."
        )
        note.setWordWrap(True)
        layout.addWidget(note)
        self.arm_controls = ArmControlsCheckBox()
        self.arm_controls.setEnabled(False)
        self.arm_controls.toggled.connect(lambda armed: self.command_requested.emit("arm", armed))
        layout.addWidget(self.arm_controls)
        self.slm_start = QPushButton("SLM Start / Pause")
        self.slm_start.setEnabled(False)
        self.slm_start.clicked.connect(lambda: self.slm_action("StartPause"))
        self.slm_stop = QPushButton("SLM Stop")
        self.slm_stop.setEnabled(False)
        self.slm_stop.clicked.connect(lambda: self.slm_action("Stop"))
        layout.addWidget(self.slm_start)
        layout.addWidget(self.slm_stop)
        refresh = QPushButton("Refresh control state")
        refresh.clicked.connect(lambda: self.command_requested.emit("refresh_control", None))
        layout.addWidget(refresh)
        self.slm_identify = QPushButton("Wake / Identify display")
        self.slm_identify.setToolTip(
            "Documented Identify: briefly lights the display and light ring. Requires armed controls; not a power-on command."
        )
        self.slm_identify.setEnabled(False)
        self.slm_identify.clicked.connect(self.identify_slm_display)
        layout.addWidget(self.slm_identify)
        save_png = QPushButton("Save original SLM PNG…")
        save_png.clicked.connect(self.save_slm_png)
        layout.addWidget(save_png)
        processed = QPushButton("Save processed display PNG…")
        processed.setToolTip(
            "Re-encoded at the selected display scale; no status overlay. Original saving above preserves received bytes."
        )
        processed.clicked.connect(self.save_processed_slm_png)
        layout.addWidget(processed)
        self.screen_context = QCheckBox("Measurement view — enable screen keys")
        self.screen_context.setEnabled(False)
        self.screen_context.toggled.connect(self.confirm_screen_context)
        layout.addWidget(self.screen_context)
        arrows = QGridLayout()
        self.screen_arrows = {}
        for direction, row, col in [("up", 0, 1), ("left", 1, 0), ("right", 1, 2), ("down", 2, 1)]:
            button = QPushButton(direction.title())
            button.setEnabled(False)
            button.setAutoRepeat(False)
            button.clicked.connect(lambda _, d=direction: self.navigate_slm_screen(d))
            self.screen_arrows[direction] = button
            arrows.addWidget(button, row, col)
        self.screen_menu = QPushButton("Menu / OK")
        self.screen_menu.setEnabled(False)
        self.screen_menu.setAutoRepeat(False)
        self.screen_menu.setToolTip(
            "Open the menu from a measurement view only; all screen keys then lock."
        )
        self.screen_menu.clicked.connect(lambda: self.navigate_slm_screen("menu"))
        arrows.addWidget(self.screen_menu, 1, 1)
        layout.addLayout(arrows)
        arrow_note = QLabel(
            "Arrows need no repeated confirmation while the measurement view is acknowledged. Menu opens once, then locks all screen keys. Return using the physical SLM and acknowledge its measurement view again. Untick before using physical menus; never navigate a setting or calibration screen remotely."
        )
        arrow_note.setWordWrap(True)
        layout.addWidget(arrow_note)
        self.recording_panel = RecordingPanel(self.settings, self.data_dir)
        layout.addWidget(self.recording_panel)
        self.audio_panel = AudioPanel(self.data_dir, self.recording_panel)
        self.audio_panel.idle.connect(self.files_idle)
        layout.addWidget(self.audio_panel)
        self.media_panel = MediaPanel(self.recording_panel, self.data_dir)
        self.audio_panel.saved.connect(self.media_panel.audio_saved)
        self.recording_panel.saved.connect(self.media_panel.video_saved)
        self.media_panel.idle.connect(self.files_idle)
        layout.addWidget(self.media_panel)
        help_button = QPushButton("How to connect an SLM")
        help_button.clicked.connect(self.connection_help)
        layout.addWidget(help_button)
        safety = QLabel(
            "Reset, calibration and menu editing are blocked. Menu / OK only opens the menu from an acknowledged measurement screen. Use the physical instrument for settings."
        )
        safety.setWordWrap(True)
        safety.setObjectName("muted")
        layout.addWidget(safety)
        self.blocked_operations = []
        for label in (
            "Reset / factory defaults — blocked",
            "Calibration / service — blocked",
            "Erase / format storage — blocked",
        ):
            blocked = QPushButton(label)
            blocked.setEnabled(False)
            blocked.setToolTip("Critical operations are blocked by the backend safety policy.")
            layout.addWidget(blocked)
            self.blocked_operations.append(blocked)
        layout.addStretch()
        self.slm_screen = ScreenPane(panel)
        # New explicit preference keys migrate away from old Fit/Smooth defaults.
        factor = float(self.settings.value("screen_scale_v2", 2))
        self.slm_screen.zoom.setCurrentIndex(max(0, self.slm_screen.zoom.findData(factor)))
        method = str(self.settings.value("screen_filter_v2", "pixel"))
        self.slm_screen.rendering.setCurrentIndex(
            max(0, self.slm_screen.rendering.findData(method))
        )
        self.slm_screen.zoom.currentIndexChanged.connect(
            lambda _: self.settings.setValue("screen_scale_v2", self.slm_screen.zoom.currentData())
        )
        self.slm_screen.rendering.currentIndexChanged.connect(
            lambda _: self.settings.setValue(
                "screen_filter_v2", self.slm_screen.rendering.currentData()
            )
        )
        self.slm_screen.connect_requested.connect(
            lambda: self.navigation.setCurrentRow(Page.CONNECTION)
        )
        return self.slm_screen

    def build_connection(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        title = QLabel("CONNECT / FIND YOUR SLM")
        title.setObjectName("heading")
        layout.addWidget(title)
        self.device_info = QLabel(
            "Enter the current IP/hostname, or find meters on this local network. No connection runs at startup."
        )
        self.device_info.setWordWrap(True)
        self.device_info.setTextFormat(Qt.TextFormat.PlainText)
        layout.addWidget(self.device_info)
        self.address = QLineEdit(str(self.settings.value("last_address", "")))
        self.address.setPlaceholderText("Current SLM IP or hostname, e.g. BK2255-serial.local")
        self.address.setAccessibleName("Instrument address")
        layout.addWidget(self.address)
        recent_row = QHBoxLayout()
        self.recent = QComboBox()
        self.recent.addItem("Recent connections…", "")
        for address in self.settings.value("recent_addresses", []):
            self.recent.addItem(address, address)
        self.recent.activated.connect(
            lambda i: self.address.setText(self.recent.itemData(i) or self.address.text())
        )
        recent_row.addWidget(self.recent, 1)
        self.password = QLineEdit()
        self.password.setEchoMode(QLineEdit.EchoMode.Password)
        self.password.setPlaceholderText("SLM password, if set (not saved)")
        self.password.setAccessibleName("SLM network password")
        recent_row.addWidget(self.password, 1)
        layout.addLayout(recent_row)
        actions = QHBoxLayout()
        self.connect_button = QPushButton("Connect SLM")
        self.connect_button.clicked.connect(
            lambda: self.select_source(
                "connect", {"address": self.address.text(), "password": self.password.text()}
            )
        )
        self.disconnect_button = QPushButton("Disconnect")
        self.disconnect_button.clicked.connect(lambda: self.select_source("disconnect"))
        help_button = QPushButton("Connection help")
        help_button.clicked.connect(self.connection_help)
        for button in (self.connect_button, self.disconnect_button, help_button):
            actions.addWidget(button)
        layout.addLayout(actions)
        self.connection_diagnostics = ConnectionDiagnostics()
        layout.addWidget(self.connection_diagnostics)
        discovery_row = QHBoxLayout()
        self.find_button = QPushButton("Find SLMs (mDNS)")
        self.find_button.clicked.connect(lambda: self.start_discovery(None))
        self.cancel_discovery = QPushButton("Cancel search")
        self.cancel_discovery.setEnabled(False)
        self.cancel_discovery.clicked.connect(
            lambda: self.discovery.cancel.set() if self.discovery else None
        )
        discovery_row.addWidget(self.find_button)
        discovery_row.addWidget(self.cancel_discovery)
        layout.addLayout(discovery_row)
        subnet_row = QHBoxLayout()
        self.subnet = QComboBox()
        self.subnet.setEditable(True)
        self.subnet.setAccessibleName("Local IPv4 subnet to search")
        networks = set()
        import ipaddress

        for interface in QNetworkInterface.allInterfaces():
            if not interface.flags() & QNetworkInterface.InterfaceFlag.IsUp:
                continue
            for entry in interface.addressEntries():
                if (
                    entry.ip().protocol() == QAbstractSocket.NetworkLayerProtocol.IPv4Protocol
                    and not entry.ip().isLoopback()
                ):
                    prefix = max(24, entry.prefixLength())
                    network = ipaddress.ip_network(
                        f"{entry.ip().toString()}/{prefix}", strict=False
                    )
                    if network.is_private:
                        networks.add(str(network))
        self.subnet.addItems(sorted(networks))
        self.subnet.lineEdit().setPlaceholderText("Local subnet, e.g. 192.168.1.0/24")
        self.scan_button = QPushButton("Search subnet")
        self.scan_button.clicked.connect(lambda: self.start_discovery(self.subnet.currentText()))
        subnet_row.addWidget(self.subnet, 1)
        subnet_row.addWidget(self.scan_button)
        layout.addLayout(subnet_row)
        self.discovery_info = QLabel(
            "mDNS finds advertised meters. Subnet search lists responding IPs; blocked/offline hosts may be absent. Select a result to fill the address."
        )
        self.discovery_info.setWordWrap(True)
        layout.addWidget(self.discovery_info)
        self.discovery_progress = QProgressBar()
        self.discovery_progress.setRange(0, 1)
        self.discovery_progress.setValue(0)
        self.discovery_progress.setTextVisible(False)
        self.discovery_progress.setAccessibleName("Discovery progress")
        layout.addWidget(self.discovery_progress)
        self.found_devices = QTableWidget(0, 3)
        self.found_devices.setHorizontalHeaderLabels(["Address", "Identity", "Discovery / status"])
        self.found_devices.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.found_devices.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.found_devices.horizontalHeader().setStretchLastSection(True)
        self.found_devices.setColumnWidth(0, 155)
        self.found_devices.setColumnWidth(1, 160)
        self.found_devices.itemSelectionChanged.connect(self.use_discovered)
        layout.addWidget(self.found_devices, 1)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(page)
        return scroll

    def connection_help(self):
        WorkflowHelp(self).exec()

    def start_discovery(self, subnet):
        if self.discovery is not None:
            return
        self.found_devices.setRowCount(0)
        self.discovery_progress.setRange(0, 0)
        self.discovery_info.setText(
            "Searching explicitly requested network scope; selecting a result will not connect automatically."
        )
        self.discovery = DiscoveryThread(subnet, self)
        self.discovery.found.connect(self.add_discovered)
        self.discovery.progress.connect(self.discovery_info.setText)
        self.discovery.failed.connect(self.discovery_info.setText)
        self.discovery.finished.connect(self.discovery_done)
        self.find_button.setEnabled(False)
        self.scan_button.setEnabled(False)
        self.cancel_discovery.setEnabled(True)
        self.discovery.start()

    def add_discovered(self, result):
        for row in range(self.found_devices.rowCount()):
            if self.found_devices.item(row, 0).text() == result.address:
                return
        if self.found_devices.rowCount() >= 256:
            return
        row = self.found_devices.rowCount()
        self.found_devices.insertRow(row)
        for column, text in enumerate(
            (result.address, result.name, result.method + " · " + result.status)
        ):
            self.found_devices.setItem(row, column, QTableWidgetItem(text))

    def use_discovered(self):
        row = self.found_devices.currentRow()
        if row >= 0:
            self.address.setText(self.found_devices.item(row, 0).text())

    def discovery_done(self):
        cancelled = self.discovery.cancel.is_set()
        self.discovery_progress.setRange(0, 1)
        self.discovery_progress.setValue(1)
        self.discovery.deleteLater()
        self.discovery = None
        self.find_button.setEnabled(True)
        self.scan_button.setEnabled(True)
        self.cancel_discovery.setEnabled(False)
        self.discovery_info.setText(
            self.discovery_info.text()
            + f" Search {'cancelled' if cancelled else 'ended'}; {self.found_devices.rowCount()} results. A response/advertisement alone does not prove usable SLM access."
        )
        if self.closing and self.worker_done:
            self.finish_close()

    def remember_connection(self, address, identity):
        self.connection_diagnostics.remember(address, identity)
        self.device_files.set_connection(
            {"address": address, "password": self.pending_connection.get("password", "")}
        )
        self.settings.setValue("last_address", address)
        recents = [address] + [
            v for v in self.settings.value("recent_addresses", []) if v != address
        ]
        self.settings.setValue("recent_addresses", recents[:10])
        self.recent.clear()
        self.recent.addItem("Recent connections…", "")
        for item in recents[:10]:
            self.recent.addItem(item, item)
        version = identity.get("Version", {})
        firmware = version.get("Firmware", "unknown") if isinstance(version, dict) else "unknown"
        self.address.setText(address)
        self.device_info.setText(
            f"Connected: {identity.get('HostName', 'SLM')} · {address} · firmware {firmware}"
        )
        self.arm_controls.setEnabled(True)

    def receive_controls(self, armed, actions):
        self.connection_diagnostics.set_controls(armed, actions)
        self.metadata_page.location.armed = armed
        self.arm_controls.blockSignals(True)
        self.arm_controls.setChecked(armed)
        self.arm_controls.blockSignals(False)
        self.arm_controls.setEnabled(bool(actions))
        self.slm_start.setEnabled(armed and "StartPause" in actions)
        self.slm_stop.setEnabled(armed and "Stop" in actions)
        self.slm_identify.setEnabled(armed and "Identify" in actions)
        self.control_actions = set(actions)
        self.screen_context.setEnabled(armed)
        if not armed:
            self.receive_keypad_state(False)
        self.update_screen_keys()
        if self.source_mode == "instrument":
            self.origin_banner.setText(
                "INSTRUMENT · " + ("SLM controls ARMED" if armed else "SLM controls disarmed")
            )

    def receive_keypad_state(self, ready):
        self.screen_context.blockSignals(True)
        self.screen_context.setChecked(ready)
        self.screen_context.blockSignals(False)
        self.update_screen_keys()

    def update_screen_keys(self):
        ready = self.arm_controls.isChecked() and self.screen_context.isChecked()
        actions = getattr(self, "control_actions", set())
        for direction, button in self.screen_arrows.items():
            button.setEnabled(ready and "Key" + direction.title() in actions)
        self.screen_menu.setEnabled(ready and "KeyMenu" in actions)

    def confirm_screen_context(self, checked):
        screen = self.slm_screen
        if checked and (
            self.source_mode != "instrument"
            or not screen.live
            or not screen.png
            or monotonic() - screen.received_at > 5
        ):
            self.receive_keypad_state(False)
            self.show_error("Inspect a fresh connected measurement screen before enabling keys.")
            return
        self.command_requested.emit(
            "screen_context",
            {
                "confirmed": checked,
                "digest": hashlib.sha256(screen.png).hexdigest(),
                "confirmed_at": monotonic(),
            },
        )

    def disable_action_buttons(self):
        for button in (
            self.slm_start,
            self.slm_stop,
            self.slm_identify,
            self.screen_menu,
            *self.screen_arrows.values(),
        ):
            button.setEnabled(False)

    def navigate_slm_screen(self, direction):
        screen = self.slm_screen
        if (
            self.source_mode != "instrument"
            or not self.arm_controls.isChecked()
            or not self.screen_context.isChecked()
            or not screen.live
            or not screen.png
            or monotonic() - screen.received_at > 5
        ):
            self.receive_keypad_state(False)
            self.show_error("Inspect a fresh connected measurement screen before navigation.")
            return
        self.disable_action_buttons()
        if direction == "menu":
            self.receive_keypad_state(False)
        self.command_requested.emit(
            "screen_menu" if direction == "menu" else "screen_arrow",
            {"direction": direction, "confirmed_at": monotonic()},
        )

    def identify_slm_display(self):
        if (
            QMessageBox.question(
                self,
                "Confirm Wake / Identify",
                "Briefly light the SLM display and light ring? This does not power on the SLM or start a measurement. Controls remain armed for this connection.",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            == QMessageBox.StandardButton.Yes
        ):
            self.command_requested.emit("identify_display", {"confirmed": True})

    def slm_action(self, action):
        if self.source_mode != "instrument" or not self.arm_controls.isChecked():
            return
        self.disable_action_buttons()
        self.command_requested.emit("slm_action", (action, 0))

    def text_page(self, title: str, content: str) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        heading = QLabel(title)
        heading.setObjectName("heading")
        layout.addWidget(heading)
        label = QLabel(content)
        label.setWordWrap(True)
        layout.addWidget(label)
        layout.addStretch()
        return page

    def build_help(self) -> QWidget:
        page = AboutPage(DISCLAIMER)
        page.help_requested.connect(self.connection_help)
        return page

    def toggle_demo(self):
        self.navigation.setCurrentRow(Page.DEMO)
        self.demo_page.toggle()

    def pause_demo(self):
        self.demo_page.toggle_pause()

    def select_source(self, name, value=None):
        if name == "demo":
            self.navigation.setCurrentRow(Page.DEMO)
            if value:
                self.demo_page.mode.setCurrentText(value)
            if not self.demo_page.device:
                self.demo_page.toggle()
            return
        if name == "connect":
            self.pending_connection = dict(value or {})
        if name in {"connect", "disconnect"}:
            self.recording_panel.set_connected(False)
            self.audio_panel.set_connection(None)
            self.device_files.set_connection(None)
        self.command_requested.emit(name, value)

    def receive_capture(self, active):
        self.capturing = active
        self.local_capture_button.setText("Stop local capture" if active else "Start local capture")
        self.update_local_status()

    def update_local_status(self):
        self.local_status.setText(
            f"LOCAL CAPTURE {'ON' if self.capturing else 'OFF'} · FILE LOGGING {'ON' if self.logging else 'OFF'} · newest {self.record_limit.value()} records shown"
        )

    def set_record_limit(self, limit):
        self.history = deque(self.history, maxlen=limit)
        if hasattr(self, "capture_chart"):
            self.capture_chart.set_limit(limit)
        while self.table.rowCount() > limit:
            self.table.removeRow(0)
        self.settings.setValue("record_limit", limit)
        self.draw_capture_trend()
        if hasattr(self, "local_status"):
            self.update_local_status()

    def draw_capture_trend(self):
        x, y = [], []
        first = self.history[0][0] if self.history else 0
        previous = None
        for timestamp, value in self.history:
            if previous is not None and not 0 < timestamp - previous <= 3:
                x.append(timestamp - first)
                y.append(float("nan"))
            x.append(timestamp - first)
            y.append(value)
            previous = timestamp
        self.curve.setData(x, y, connect="finite")

    def receive_sample(self, sample: Sample) -> None:
        if sample.origin != "instrument":
            return
        self.latest = sample
        self.connection_diagnostics.sample_seen(sample)
        self.last_received = monotonic()
        self.update_freshness()
        self.frequency_page.update_sample(sample)
        self.spectrum_preview.update_frame(self.frequency_page.live_frame)
        self.level_bar.update_level(
            sample.values.get("LAF"),
            self.settings.value("dashboard_range", "20–140 dB") == "20–140 dB",
        )
        self.metadata_page.update_fields(sample.metadata)
        self.metadata_page.location.update_sample(sample)
        a, c = sample.values.get("LAeq"), sample.values.get("LCeq")
        self.local_calculations.setText(
            "Local calculation (polled inputs; not an SLM output) · LCeq − LAeq: "
            + (f"{c - a:.1f} dB" if a is not None and c is not None else "unavailable")
        )
        for key, tile in self.tiles.items():
            value = sample.values.get(key)
            tile.value.setText("N/A" if value is None else f"{value:.1f}")
        self.footer.setText(
            f"{sample.timestamp.astimezone():%H:%M:%S %Z}  ·  {sample.state}  ·  {sample.origin}  ·  {sample.quality}"
        )

    def receive_captured(self, sample):
        if sample.origin != "instrument":
            return
        self.capture_chart.append(
            TrendPoint.create(
                sample.timestamp, sample.values, sample.origin, sample.state, sample.quality
            )
        )
        laf = sample.values.get("LAF")
        self.history.append((sample.timestamp.timestamp(), laf if finite(laf) else float("nan")))
        self.draw_capture_trend()
        if self.table.rowCount() >= self.record_limit.value():
            self.table.removeRow(0)
        row = self.table.rowCount()
        self.table.insertRow(row)
        values = [
            sample.timestamp.isoformat(timespec="seconds"),
            f"{sample.elapsed_s:.1f}",
            "N/A" if laf is None else f"{laf:.1f}",
            "N/A" if sample.values.get("LAeq") is None else f"{sample.values['LAeq']:.1f}",
            sample.state,
            sample.origin,
        ]
        values += [
            "N/A" if sample.values.get(p.id) is None else f"{sample.values[p.id]:.1f}"
            for p in self.extra_columns
        ]
        for column, value in enumerate(values):
            self.table.setItem(row, column, QTableWidgetItem(value))
        if self.auto_scroll.isChecked():
            self.table.scrollToBottom()

    def receive_status(self, mode: str, detail: str) -> None:
        self.connection_diagnostics.set_mode(mode)
        self.device_info.setText(mode.upper() + " · " + detail)
        if mode != "stale":
            self.recording_panel.set_connected(mode == "instrument")
        else:
            self.recording_panel.start_button.setEnabled(False)
        if mode in {"disconnected", "connecting", "stale"}:
            self.device_files.set_connection(None)
        elif mode == "instrument" and not self.device_files.connection:
            self.device_files.set_connection(
                self.pending_connection or {"address": self.address.text()}
            )
        self.audio_panel.set_connection(
            (self.pending_connection or {"address": self.address.text()})
            if mode == "instrument"
            else None
        )
        previous_mode = self.source_mode
        self.source_mode = mode
        prefixes = {
            "simulation": "DEMO — SYNTHETIC DATA",
            "instrument": "INSTRUMENT",
            "stale": "STALE DATA",
            "connecting": "CONNECTING",
            "disconnected": "NOT CONNECTED",
        }
        self.origin_banner.setText(prefixes.get(mode, mode) + "  ·  " + detail)
        self.pause_button.setEnabled(mode == "simulation")
        self.pause_button.setText("Resume demo" if "paused" in detail else "Pause demo")
        self.demo_button.setText("Stop demo" if mode == "simulation" else "Start demo")
        self.demo_mode.setEnabled(mode != "simulation")
        self.local_capture_button.setEnabled(mode == "instrument" or self.capturing)
        self.log_button.setEnabled(mode == "instrument" or self.logging)
        self.connect_button.setEnabled(mode != "connecting")
        if mode == "connecting" or (
            mode in {"simulation", "instrument"} and previous_mode == "disconnected"
        ):
            self.latest = None
            self.history.clear()
            self.curve.setData([], [])
            self.table.setRowCount(0)
            self.capture_chart.set_points([])
        if mode in {"disconnected", "connecting", "stale"}:
            self.latest = None
            for tile in self.tiles.values():
                tile.value.setText("—")
            self.last_received = None
            self.dashboard_status.setText("SLM · " + mode + " · no fresh sample")
            self.level_bar.update_level(None)
            self.frequency_page.update_spectra({})
            self.spectrum_preview.update_frame(self.frequency_page.live_frame)
            self.metadata_page.update_fields({})
            self.metadata_page.location.clear_instrument()
            self.local_calculations.setText(
                "Local calculation · unavailable (no fresh instrument data)"
            )

    def toggle_logging(self) -> None:
        if self.logging:
            self.command_requested.emit("log_stop", None)
        else:
            if self.source_mode != "instrument":
                self.show_error("Connect an instrument before starting a local log.")
                return
            try:
                report = self.metadata_page.report.snapshot()
                filename = log_filename(
                    report, bool(self.metadata_page.report.naming.currentIndex())
                )
            except ValueError as exc:
                self.show_error(str(exc))
                return
            destination = self.data_dir / "sessions" / filename
            self.command_requested.emit(
                "log_start", {"path": str(destination), "report_context": report}
            )

    def receive_session(self, path: str, active: bool, count: int) -> None:
        self.session_path, self.logging = path, active
        self.log_button.setText("Stop file logging" if active else "Start file logging")
        self.session_info.setText(f"{'Logging' if active else 'Saved'} · {count} samples\n{path}")
        self.update_local_status()
        self.refresh_export_preview()

    def open_session(self) -> None:
        if self.export_job is not None:
            return
        if self.logging:
            self.show_error("Stop local logging before selecting a different session.")
            return
        path, _ = QFileDialog.getOpenFileName(
            self, "Select B&KG session", str(self.data_dir / "sessions"), "B&KG sessions (*.sqlite)"
        )
        if path:
            self.session_path = path
            self.session_info.setText("Selected for export:\n" + path)
            self.refresh_export_preview()
            self.history_browser.open_path(path)

    def export_current(self) -> None:
        if self.export_job is not None:
            return
        if not self.session_path:
            self.show_error("Log a session or select an existing session first.")
            return
        try:
            format_name = self.current_export_profile().format_name
        except ValueError as exc:
            self.show_error(str(exc))
            return
        target, _ = QFileDialog.getSaveFileName(
            self,
            "Export session to a new file",
            str(self.data_dir / f"BnKG-export-{datetime.now():%Y%m%d-%H%M%S}.{format_name}"),
            f"{format_name.upper()} (*.{format_name})",
        )
        if target:
            self.start_export(self.session_path, target, format_name)

    def start_export(self, database, target, format_name):
        if self.export_job is not None:
            return
        try:
            value = self.current_export_profile(format_name)
        except ValueError as exc:
            self.show_error(str(exc))
            return
        self.export_job = ExportJob(
            Path(database), Path(target), value.format_name, value.options(), self
        )
        self.set_export_busy(True)
        self.export_job.completed.connect(self.export_finished)
        self.export_job.failed.connect(
            lambda message: self.export_status.setText("Export failed: " + message)
        )
        self.export_job.cancelled.connect(
            lambda: self.export_status.setText("Export cancelled; no destination published.")
        )
        self.export_job.progress.connect(self.export_progress_changed)
        self.export_job.finished.connect(self.export_idle)
        self.export_button.setEnabled(False)
        self.cancel_export_button.setEnabled(True)
        self.export_status.setText("Preparing a consistent database snapshot…")
        self.export_job.start()

    def cancel_export(self):
        if self.export_job:
            self.export_job.requestInterruption()
            self.export_status.setText("Cancelling export; waiting for safe cleanup…")

    def export_progress_changed(self, done, total, phase):
        self.export_progress.setRange(0, max(1, total))
        self.export_progress.setValue(done)
        self.export_status.setText(f"{phase}: {done:,} / {total:,}")

    def export_finished(self, path: str, count: int) -> None:
        self.export_status.setText(f"Export complete: {count} rows → {path}")
        self.footer.setText(self.export_status.text())

    def export_idle(self):
        self.export_job.deleteLater()
        self.export_job = None
        self.set_export_busy(False)
        self.export_button.setEnabled(True)
        self.cancel_export_button.setEnabled(False)
        self.files_idle()

    def save_slm_png(self):
        if not self.slm_screen.png:
            self.show_error("Connect an SLM and receive a screen image first.")
            return
        path, _ = QFileDialog.getSaveFileName(
            self,
            "Save original SLM image (last received)",
            str(self.data_dir / f"BnKG-SLM-Screen-{datetime.now():%Y%m%d-%H%M%S-%f}.png"),
            "PNG (*.png)",
        )
        if path:
            try:
                self.slm_screen.save_png(path)
                self.footer.setText("Original received PNG saved: " + path)
            except (OSError, ValueError) as exc:
                self.show_error(str(exc))

    def show_recording_status(self, text):
        self.recording_notice.setText("SCREEN RECORDING · " + text)
        self.recording_notice.setVisible(self.recording_panel.job is not None)

    def save_processed_slm_png(self):
        path, _ = QFileDialog.getSaveFileName(
            self,
            "Save processed display PNG (no status overlay)",
            str(self.data_dir / f"BnKG-SLM-Processed-{datetime.now():%Y%m%d-%H%M%S-%f}.png"),
            "PNG (*.png)",
        )
        if path:
            try:
                self.slm_screen.save_processed_png(path)
                self.footer.setText(
                    "Processed display PNG saved: "
                    + path
                    + " · Check display freshness; original saving is separate."
                )
            except (OSError, ValueError) as exc:
                self.show_error(str(exc))

    def screenshot(self) -> None:
        path, _ = QFileDialog.getSaveFileName(
            self,
            "Save workspace screenshot",
            str(self.data_dir / f"BnKG-{datetime.now():%Y%m%d-%H%M%S}.png"),
            "PNG (*.png)",
        )
        if path:
            if not self.grab().save(path, "PNG"):
                self.show_error("Screenshot could not be saved.")
            else:
                self.footer.setText("Screenshot saved: " + path)

    def show_error(self, detail: str) -> None:
        self.export_button.setEnabled(self.export_job is None)
        self.footer.setText(detail)
        if not self.closing:
            QMessageBox.warning(self, "B&KG", detail)

    def apply_theme(self, name):
        dark = name == "Dark" or (
            name == "System" and QApplication.styleHints().colorScheme() == Qt.ColorScheme.Dark
        )
        background, panel, foreground, muted, edge = (
            ("#171c1b", "#222a27", "#edf0e9", "#b0bab3", "#48544c")
            if dark
            else ("#f1f3ee", "#ffffff", "#17241e", "#506157", "#bdc8be")
        )
        color = self.color_theme.currentText()
        palettes = {
            "B&KG": ("#a6d39a", "#286238"),
            "Colorful": ("#e7b66f", "#885208"),
            "Blue": ("#8dc6ed", "#205c88"),
            "Red": ("#f2a1a1", "#9d3333"),
            "Green": ("#89d6b2", "#186440"),
        }
        accent = palettes.get(color, palettes["B&KG"])[0 if dark else 1]
        palette = QPalette()
        for role, value in (
            (QPalette.ColorRole.Window, background),
            (QPalette.ColorRole.Base, panel),
            (QPalette.ColorRole.WindowText, foreground),
            (QPalette.ColorRole.Text, foreground),
            (QPalette.ColorRole.Button, panel),
            (QPalette.ColorRole.ButtonText, foreground),
            (QPalette.ColorRole.Highlight, accent),
            (QPalette.ColorRole.HighlightedText, background),
            (QPalette.ColorRole.Link, accent),
            (QPalette.ColorRole.LinkVisited, accent),
        ):
            palette.setColor(role, QColor(value))
        self.setPalette(palette)
        self.setStyleSheet(f"""
            QWidget {{ background: {background}; color: {foreground}; font-family: 'Segoe UI'; font-size: 10pt; }}
            QFrame#sidebar {{ background: {panel}; border-right: 1px solid {edge}; }}
            #sidebar QLabel, #navigation {{ background: {panel}; }}
            QLabel#brand {{ font-size: 29pt; font-weight: 750; color: {accent}; }}
            QLabel#heading {{ font-size: 17pt; font-weight: 650; color: {accent}; }}
            QLabel#subheading {{ font-size: 11pt; font-weight: 600; color: {accent}; }}
            QLabel#muted {{ color: {muted}; }}
            QLabel#banner {{ background: {panel}; border-left: 3px solid #ba813e; padding: 9px; }}
            QFrame#tile {{ background: {panel}; border: 1px solid {edge}; border-top: 2px solid {edge}; border-radius: 2px; }}
            #tile QLabel {{ background: {panel}; }}
            QLabel#reading {{ font-family: 'Consolas'; font-size: {max(18, min(40, self.settings.value("reading_font_size", 28, type=int)))}pt; font-weight: 600; color: {accent}; }}
            QPushButton, QComboBox, QLineEdit, QSpinBox {{ padding: 7px 9px; background: {panel}; border: 1px solid {edge}; border-radius: 2px; }}
            QPushButton:hover, QPushButton:checked {{ color: {accent}; border-color: {accent}; }}
            QPushButton:disabled {{ color: {muted}; }}
            QPushButton:focus, QLineEdit:focus, QComboBox:focus {{ border: 2px solid {accent}; }}
            QListWidget {{ border: none; outline: none; }}
            QListWidget::item {{ padding: 11px 6px; margin: 2px 0; }}
            QListWidget::item:selected {{ color: {accent}; border-left: 3px solid {accent}; background: {background}; }}
            QScrollArea, QTextBrowser, QTableWidget {{ border: none; }}
            QTextBrowser {{ color: {foreground}; background: {panel}; }}
            #screenOverlay {{ background: {panel}; color: {foreground}; }}
            QLabel#construction {{ font-size: 9pt; color: {muted}; }}
            QHeaderView::section {{ padding: 8px; background: {panel}; color: {foreground}; border: 1px solid {edge}; }}
            QCheckBox {{ spacing: 10px; padding: 7px; }}
            #instrumentDisplay {{ border: 1px solid {edge}; }}
        """)
        if color == "Colorful":
            colors = (
                ["#8dc6ed", "#a6d39a", "#e7b66f", "#d0adeb"]
                if dark
                else ["#205c88", "#286238", "#885208", "#774599"]
            )
        else:
            colors = [accent]
        for index, tile in enumerate(self.tiles.values()):
            tile.value.setStyleSheet(f"color: {colors[index % len(colors)]};")
        self.plot.setBackground(background)
        self.curve.setPen(pg.mkPen(accent, width=2))
        for axis in ("left", "bottom"):
            self.plot.getAxis(axis).setTextPen(foreground)
            self.plot.getAxis(axis).setPen(edge)
        self.plot.setLabel("left", "LAF", units="dB", color=foreground)
        self.plot.setLabel("bottom", "PC receipt time", units="s", color=foreground)
        # QLabel rich-text links otherwise retain Qt's dark-blue default in dark mode.
        import re

        for link in self.findChildren(QLabel):
            if "<a href=" in link.text() or "<a style=" in link.text():
                html = re.sub(
                    r'<a (?:style="[^"]*" )?href=', f'<a style="color: {accent}" href=', link.text()
                )
                link.setText(html)
        self.capture_chart.set_theme(background, foreground, accent)
        self.history_browser.chart.set_theme(background, foreground, accent)
        self.history_browser.saved_spectrum.set_theme(background, foreground, accent)
        self.spectrum_preview.set_theme(background, foreground, accent)
        self.frequency_page.set_theme(background, foreground, accent)
        self.demo_page.frequency.set_theme(background, foreground, accent)
        self.settings.setValue("theme", name)
        self.settings.setValue("color_theme", color)
        self.theme.blockSignals(True)
        self.theme.setCurrentText(name)
        self.theme.blockSignals(False)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if not hasattr(self, "navigation"):
            return
        narrow = self.width() < 900
        self.sidebar.setVisible(not narrow)
        self.mobile_navigation.setVisible(narrow)
        self.main_layout.setContentsMargins(12 if narrow else 24, 12, 12 if narrow else 24, 12)
        columns = 2 if self.width() < 600 else 3
        while self.local_controls.count():
            self.local_controls.takeAt(0)
        for i, widget in enumerate(self.local_widgets):
            self.local_controls.addWidget(widget, i // columns, i % columns)
        self.update_visible()

    def closeEvent(self, event: QCloseEvent) -> None:
        if self.thread_finished:
            event.accept()
            return
        event.ignore()
        if not self.closing:
            if not self.history_browser.review_panel.confirm_discard():
                return
            self.closing = True
            self.demo_page.stop()
            self.device_files.stop()
            self.history_browser.stop()
            self.bkc_panel.stop()
            self.cancel_export()
            self.recording_panel.cancel()
            self.audio_panel.stop()
            self.media_panel.shutdown()
            if self.slm_screen.fullscreen_dialog:
                self.slm_screen.fullscreen_dialog.close()
            self.settings.setValue("geometry", self.saveGeometry())
            self.settings.sync()
            self.centralWidget().setEnabled(False)
            self.footer.setText("Closing session and waiting for the current operation to finish…")
            if self.discovery:
                self.discovery.cancel.set()
            self.thread.requestInterruption()
            self.shutdown_requested.emit()

    def worker_closed(self):
        self.worker_done = True
        if self.discovery is None:
            self.finish_close()

    def files_idle(self):
        if self.closing and self.worker_done and self.discovery is None:
            self.finish_close()

    def finish_close(self) -> None:
        if (
            self.device_files.query is not None
            or self.history_browser.query is not None
            or self.export_job is not None
            or self.recording_panel.job is not None
            or self.audio_panel.job is not None
            or self.media_panel.job is not None
            or self.bkc_panel.job is not None
        ):
            return
        self.thread_finished = True
        self.close()

    def diagnostic_snapshot(self) -> str:
        return json.dumps(
            {
                "version": __version__,
                "source": self.source_mode,
                "logging": self.logging,
                "session": self.session_path,
            }
        )
