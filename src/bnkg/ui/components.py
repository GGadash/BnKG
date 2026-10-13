"""Reusable appearance and SLM display widgets."""

import io
import struct
import time

from PIL import Image
from PIL.ImageQt import ImageQt
from PySide6.QtCore import QBuffer, QEvent, QIODevice, Qt, QTimer, Signal
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QBoxLayout,
    QButtonGroup,
    QCheckBox,
    QComboBox,
    QDialog,
    QFrame,
    QGraphicsOpacityEffect,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

CONNECTION_HELP = """Connect an SLM

1. Connect this PC and the SLM to the same local network: Wi-Fi, the instrument hotspot, or supported USB-C/Ethernet networking.
2. On the SLM open Menu > System settings > Network settings. Check the current Wi-Fi or Ethernet IP address; DHCP can change it.
3. Use Find SLMs (mDNS), select a result, then Connect. Or type the current IP/hostname. Recent addresses are shortcuts, not proof that the same meter is still there.
4. If discovery finds nothing, try the current IP or select a local subnet and Search subnet. Firewalls, guest isolation and different subnets can block discovery. Results cannot guarantee every connected device is visible.
5. Web-XI requires the installed/enabled BZ-7400 Open Interface licence for full access. If the SLM has a network password, enter it in the password box; B&KG does not save it.
6. For the mirrored screen enable Web server display on the physical SLM under Network settings. B&KG never changes that setting automatically. The PNG route is verified on this 2255 firmware 1.3; other versions may differ.

Local work versus the SLM
Monitoring updates live readings only. In Data table, Start local capture adds table/trend records. Start file logging also starts capture and creates a timestamped SQLite file. Stop file logging leaves capture running. Stop local capture or Disconnect stops instrument capture and closes its log. Demo Lab is independent and has simple CSV saving; its Pause/Stop produces no new demo records and does not affect instrument monitoring. The table keeps only the newest selected number of rows; the file retains the complete logged session.

SLM controls are separate. Arm them for each connection before a deliberate action. Start/Pause and Stop change the real measurement without repeated confirmation dialogs while armed. Successful actions keep arming for this connection. After an uncertain response no action is retried: inspect/refresh state and deliberately re-arm. Wake / Identify briefly lights the display and light ring and also requires arming. It is not a power-on command. Acknowledge the measurement view once for arrows. Menu / OK only opens a menu and then locks the keypad; return physically before acknowledging the measurement screen again. Menu editing, calibration, reset and generic settings writes remain blocked. Metadata offers a separately reviewed location-text transfer to an already enabled Text slot, with two confirmations and read-back; it does not change native GPS.

Frequency Analysis uses actual current and total SLM outputs. Metadata lists available fields and access flags; GPS injection/project-name setters are not verified. The SLM screen retains the last PNG with a dim overlay when stale/disconnected. Save original SLM PNG keeps native bytes. Optional local screen recording preserves PNG frames/timing; external FFmpeg can create a processed MP4. Instrument FLAC capture, local playback, native AAC/Opus export and receipt-aligned paired MP4 are available; timing/quality limitations are shown in their controls.
"""


class AppearanceSelector(QWidget):
    currentTextChanged = Signal(str)

    def __init__(self):
        super().__init__()
        self.group = QButtonGroup(self)
        self.buttons = {}
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        for name in ("System", "Dark", "Light"):
            button = QPushButton({"System": "▣ System", "Dark": "☾ Dark", "Light": "☀ Light"}[name])
            button.setProperty("mode", name)
            button.setCheckable(True)
            button.setAccessibleName(name + " appearance")
            button.clicked.connect(lambda checked, n=name: self.currentTextChanged.emit(n))
            self.group.addButton(button)
            self.buttons[name] = button
            layout.addWidget(button)
        self.buttons["Dark"].setChecked(True)

    def currentText(self):
        return self.group.checkedButton().property("mode")

    def setCurrentText(self, name):
        name = name if name in self.buttons else "Dark"
        changed = self.currentText() != name
        self.buttons[name].setChecked(True)
        if changed:
            self.currentTextChanged.emit(name)


class ArmControlsCheckBox(QCheckBox):
    """Accessible check box with a full-width click target and explicit armed state."""

    def __init__(self):
        super().__init__("Arm SLM controls — OFF")
        self.toggled.connect(
            lambda checked: self.setText(
                "SLM controls — ARMED" if checked else "Arm SLM controls — OFF"
            )
        )
        self.setMinimumHeight(62)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setStyleSheet("""
            QCheckBox { padding: 12px; spacing: 14px; border: 2px solid #67716b;
                        border-radius: 7px; background: #303833; color: #d7ddd8;
                        font-size: 15px; font-weight: 600; }
            QCheckBox:checked { background: #285c34; border-color: #a6d695; color: #ffffff; }
            QCheckBox:focus { border-color: #e6b86a; }
            QCheckBox:disabled { background: #303430; color: #919991; border-color: #505950; }
            QCheckBox::indicator { width: 26px; height: 26px; }
        """)

    def hitButton(self, pos):
        return self.rect().contains(pos)

    def setChecked(self, checked):
        super().setChecked(checked)
        self.setText("SLM controls — ARMED" if checked else "Arm SLM controls — OFF")


class ScreenPane(QWidget):
    connect_requested = Signal()
    image_changed = Signal(bytes)
    status_changed = Signal(str)

    def __init__(self, controls):
        super().__init__()
        self.frame = QFrame()
        self.frame.setObjectName("instrumentDisplay")
        content = QGridLayout(self.frame)
        self.image = QLabel("SLM DISPLAY\n\nNo instrument connected")
        self.image.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.image.setMinimumSize(1, 1)
        self.image.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Ignored)
        self.opacity = QGraphicsOpacityEffect(self.image)
        self.image.setGraphicsEffect(self.opacity)
        self.viewport = QScrollArea()
        self.viewport.setWidgetResizable(False)
        self.viewport.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.viewport.setWidget(self.image)
        self.viewport.viewport().installEventFilter(self)
        content.addWidget(self.viewport, 1, 0)
        content.setRowStretch(1, 1)
        overlay = QWidget()
        overlay.setObjectName("screenOverlay")
        row = QVBoxLayout(overlay)
        self.status = QLabel("Disconnected — connect an SLM to view its display")
        self.status.setWordWrap(True)
        row.addWidget(self.status)
        self.connect_button = QPushButton("Connect SLM…")
        self.connect_button.clicked.connect(self.connect_requested.emit)
        row.addWidget(self.connect_button)
        content.addWidget(overlay, 0, 0, Qt.AlignmentFlag.AlignTop)
        self.pixmap = QPixmap()
        self.png = b""
        self.received_at = 0.0
        self.changed_at = 0.0
        self.live = False
        self.watchdog = QTimer(self)
        self.watchdog.setInterval(1000)
        self.watchdog.timeout.connect(self.check_age)
        self.watchdog.start()
        self.flow = QBoxLayout(QBoxLayout.Direction.LeftToRight, self)
        self.flow.setContentsMargins(0, 0, 0, 0)
        self.controls = QScrollArea()
        self.controls.setWidgetResizable(True)
        self.controls.setWidget(controls)
        # The control column scrolls vertically; stack long tool rows rather than
        # letting their combined button widths hide the right-hand keypad.
        for row in controls.findChildren(QHBoxLayout):
            row.setDirection(QBoxLayout.Direction.TopToBottom)
        self.controls.setMinimumWidth(380)
        self.fullscreen_dialog = None
        display = QWidget()
        column = QVBoxLayout(display)
        column.setContentsMargins(0, 0, 0, 0)
        tools = QGridLayout()
        self.zoom = QComboBox()
        for label, factor in [("Fit", 0), ("100%", 1), ("200%", 2), ("400%", 4)]:
            self.zoom.addItem(label, factor)
        self.rendering = QComboBox()
        self.zoom.setCurrentIndex(2)
        for label, method in [
            ("Pixel — Nearest Neighbor", "pixel"),
            ("Sharp — Lanczos", "sharp"),
            ("Smooth — Bicubic", "smooth"),
        ]:
            self.rendering.addItem(label, method)
        self.zoom.currentIndexChanged.connect(self.scale_image)
        self.rendering.currentIndexChanged.connect(self.scale_image)
        self.hide_controls = QPushButton("Hide controls")
        self.hide_controls.setCheckable(True)
        self.hide_controls.toggled.connect(self.toggle_controls)
        self.fullscreen_button = QPushButton("Fullscreen display")
        self.fullscreen_button.clicked.connect(self.open_fullscreen)
        tools.addWidget(self.zoom, 0, 0)
        tools.addWidget(self.rendering, 0, 1)
        tools.addWidget(self.hide_controls, 1, 0)
        tools.addWidget(self.fullscreen_button, 1, 1)
        column.addLayout(tools)
        column.addWidget(self.frame, 1)
        self.flow.addWidget(display, 2)
        self.flow.addWidget(self.controls, 1)

    def set_image(self, data):
        if len(data) < 24 or data[:8] != b"\x89PNG\r\n\x1a\n":
            self.set_status("Invalid screen image")
            return
        width, height = struct.unpack(">II", data[16:24])
        if not (0 < width <= 2048 and 0 < height <= 2048):
            self.set_status("Screen image dimensions exceed the display limit")
            return
        pixmap = QPixmap()
        if not pixmap.loadFromData(data, "PNG"):
            self.set_status("Could not decode screen image")
            return
        now = time.monotonic()
        if data != self.png:
            self.changed_at = now
        self.received_at = now
        self.png = bytes(data)
        self.pixmap = pixmap
        self.scale_image()
        self.image_changed.emit(self.png)

    def set_status(self, text):
        self.live = text.startswith("Live SLM")
        self.status.setText(text)
        self.opacity.setOpacity(1.0 if self.live else 0.45)
        self.connect_button.setVisible("connect" in text.lower() and not self.live)
        if self.pixmap.isNull():
            self.image.setText("SLM DISPLAY\n\nWaiting for an image")
        self.check_age()
        self.status_changed.emit(text)

    def check_age(self):
        if not self.live or not self.received_at:
            return
        age = time.monotonic() - self.received_at
        unchanged = time.monotonic() - self.changed_at
        if age > 5:
            self.status.setText(f"Display not updating — last image received {age:.0f}s ago")
            self.opacity.setOpacity(0.45)
        elif unchanged > 10:
            self.status.setText(
                f"Display not updating — image unchanged for {unchanged:.0f}s; display may be off or static"
            )
            self.opacity.setOpacity(0.65)

    def save_png(self, path):
        if not self.png:
            raise ValueError("No instrument screen image has been received.")
        with open(path, "xb") as handle:
            handle.write(self.png)

    def toggle_controls(self, hidden):
        self.controls.setVisible(not hidden)
        self.hide_controls.setText("Show controls" if hidden else "Hide controls")

    def transformed_pixmap(self):
        if self.pixmap.isNull():
            raise ValueError("No instrument screen image has been received.")
        factor = self.zoom.currentData()
        size = (self.pixmap.size() * factor) if factor else self.viewport.viewport().size()
        size = self.pixmap.size().scaled(size, Qt.AspectRatioMode.KeepAspectRatio)
        width, height = max(1, size.width()), max(1, size.height())
        # Bounded instrument PNGs; cache the last transform for resize/repaint events.
        key = (self.pixmap.cacheKey(), width, height, self.rendering.currentData())
        if getattr(self, "_render_key", None) != key:
            filters = {
                "pixel": Image.Resampling.NEAREST,
                "sharp": Image.Resampling.LANCZOS,
                "smooth": Image.Resampling.BICUBIC,
            }
            with Image.open(io.BytesIO(self.png)) as original:
                resized = original.convert("RGBA").resize((width, height), filters[key[-1]])
                self._rendered = QPixmap.fromImage(ImageQt(resized).copy())
            self._render_key = key
        return self._rendered

    def save_processed_png(self, path):
        buffer = QBuffer()
        buffer.open(QIODevice.OpenModeFlag.WriteOnly)
        if not self.transformed_pixmap().save(buffer, "PNG"):
            raise OSError("Could not encode processed PNG.")
        with open(path, "xb") as handle:
            handle.write(bytes(buffer.data()))

    def open_fullscreen(self):
        if self.fullscreen_dialog:
            self.fullscreen_dialog.raise_()
            return
        dialog = QDialog(self)
        dialog.setWindowTitle("SLM display — Escape to return")
        dialog.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        layout = QVBoxLayout(dialog)
        view = ScreenPane(QWidget())
        view.zoom.setCurrentIndex(self.zoom.currentIndex())
        view.rendering.setCurrentIndex(self.rendering.currentIndex())
        view.controls.hide()
        view.hide_controls.hide()
        view.fullscreen_button.hide()
        layout.addWidget(view)
        close = QPushButton("Return to workspace (Esc)")
        close.clicked.connect(dialog.reject)
        layout.addWidget(close)
        if self.png:
            view.set_image(self.png)
        view.set_status(self.status.text())
        # A retained frame must keep its original age in the detached view.
        view.received_at, view.changed_at = self.received_at, self.changed_at
        self.image_changed.connect(view.set_image)
        self.status_changed.connect(view.set_status)
        dialog.destroyed.connect(lambda: setattr(self, "fullscreen_dialog", None))
        self.fullscreen_dialog = dialog
        dialog.showFullScreen()

    def scale_image(self, *_):
        if not self.pixmap.isNull():
            fit = not self.zoom.currentData()
            policy = (
                Qt.ScrollBarPolicy.ScrollBarAlwaysOff
                if fit
                else Qt.ScrollBarPolicy.ScrollBarAsNeeded
            )
            self.viewport.setHorizontalScrollBarPolicy(policy)
            self.viewport.setVerticalScrollBarPolicy(policy)
            rendered = self.transformed_pixmap()
            self.image.setFixedSize(rendered.size())
            self.image.setPixmap(rendered)

    def eventFilter(self, watched, event):
        if watched is self.viewport.viewport() and event.type() == QEvent.Type.Resize:
            if hasattr(self, "zoom"):
                self.scale_image()
        return super().eventFilter(watched, event)

    def resizeEvent(self, event):
        self.flow.setDirection(
            QBoxLayout.Direction.TopToBottom
            if self.width() < 640
            else QBoxLayout.Direction.LeftToRight
        )
        super().resizeEvent(event)
        self.scale_image()
