"""Explicit location draft and reviewed custom-text metadata transfer."""

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from bnkg.core.location import DEFAULT_LATITUDE, DEFAULT_LONGITUDE, coordinate_text


class LocationPanel(QWidget):
    command = Signal(str, object)

    def __init__(self):
        super().__init__()
        self.source = "manual"
        self.sample = None
        self.armed = False
        self.connected = False
        layout = QVBoxLayout(self)
        title = QLabel("LOCATION → SLM TEXT METADATA")
        title.setObjectName("subheading")
        layout.addWidget(title)
        self.info = QLabel(
            "Enter coordinates or copy a valid instrument location; no location is preset. Native GPS fields remain read-only. Automatic PC/phone acquisition is not implemented."
        )
        self.info.setWordWrap(True)
        layout.addWidget(self.info)
        row = QHBoxLayout()
        self.latitude = QLineEdit(DEFAULT_LATITUDE)
        self.latitude.setAccessibleName("Latitude, decimal degrees")
        self.longitude = QLineEdit(DEFAULT_LONGITUDE)
        self.longitude.setAccessibleName("Longitude, decimal degrees")
        for text, widget in (("Latitude", self.latitude), ("Longitude", self.longitude)):
            row.addWidget(QLabel(text))
            row.addWidget(widget)
            widget.textEdited.connect(self.edited)
        layout.addLayout(row)
        self.map_link = QLabel()
        self.map_link.setWordWrap(True)
        self.map_link.setOpenExternalLinks(True)
        layout.addWidget(self.map_link)
        self.copy_map = QPushButton("Copy map link")
        self.copy_map.clicked.connect(lambda: QApplication.clipboard().setText(self.map_url))
        layout.addWidget(self.copy_map)
        self.map_url = ""
        self.latitude.textChanged.connect(self.refresh_map)
        self.longitude.textChanged.connect(self.refresh_map)
        self.refresh_map()
        row = QHBoxLayout()
        self.use_slm = QPushButton("Use current SLM coordinates")
        self.use_slm.clicked.connect(self.copy_slm)
        self.slot = QComboBox()
        for n in range(1, 10):
            self.slot.addItem(f"Metadata slot {n}", n)
        row.addWidget(self.use_slm)
        row.addWidget(self.slot)
        layout.addLayout(row)
        self.preview = QPushButton("Preview location transfer…")
        self.preview.clicked.connect(self.request_preview)
        layout.addWidget(self.preview)
        note = QLabel(
            "On the SLM: enable Metadata and a spare slot, choose Text and name it (for example GPS coordinates). Leave the meter idle with no pending result. B&KG replaces only that slot's text after two confirmations. It does not rename/enable slots, change native GPS or save a measurement. Coordinate writes are recorded locally even when measurement logging is off."
        )
        note.setWordWrap(True)
        layout.addWidget(note)
        self.clear_instrument()

    def refresh_map(self, *_):
        try:
            lat, lon = coordinate_text(self.latitude.text(), self.longitude.text()).split(", ")
            self.map_url = (
                f"https://www.openstreetmap.org/?mlat={lat}&mlon={lon}#map=16/{lat}/{lon}"
            )
            basis = (
                "SLM-reported draft"
                if self.source == "slm-reported"
                else "Manual draft; not an acquired fix"
            )
            self.map_link.setText(
                f'{basis} · <a href="{self.map_url}">Open coordinates in OpenStreetMap</a>. Opening sends these coordinates to the map provider. No map is fetched automatically.'
            )
        except ValueError:
            self.map_url = ""
            self.map_link.setText(
                "Map link unavailable: enter valid coordinates. The current draft has not changed native GPS."
            )
        self.copy_map.setEnabled(bool(self.map_url))

    def edited(self, _):
        self.source = "manual"
        self.refresh_map()
        self.info.setText(
            "Manually entered location; not an acquired fix. Verify that it describes the SLM position."
        )

    def clear_instrument(self):
        self.sample = None
        self.connected = False
        self.preview.setEnabled(False)
        self.use_slm.setEnabled(False)

    def update_sample(self, sample):
        self.sample = sample
        self.connected = True
        self.preview.setEnabled(True)
        self.use_slm.setEnabled(True)
        for i in range(9):
            name = sample.metadata.get(f"Metadata{i + 1}Name", {}).get("value", "")
            self.slot.setItemText(i, f"{i + 1}: {name}" if name else f"Metadata slot {i + 1}")

    def copy_slm(self):
        if self.sample is None:
            return
        lat = self.sample.metadata.get("Latitude", {}).get("value")
        lon = self.sample.metadata.get("Longitude", {}).get("value")
        try:
            text = coordinate_text(lat, lon)
        except ValueError:
            self.info.setText("No usable SLM coordinates are available. Manual draft retained.")
            return
        a, b = text.split(", ")
        self.latitude.setText(a)
        self.longitude.setText(b)
        self.source = "slm-reported"
        self.refresh_map()
        self.info.setText(
            f"Copied SLM-reported coordinates received at {self.sample.timestamp.isoformat()}. This is PC receipt time, not a verified GPS fix timestamp."
        )

    def request_preview(self):
        try:
            coordinate_text(self.latitude.text(), self.longitude.text())
        except ValueError as exc:
            self.info.setText(str(exc))
            return
        self.command.emit(
            "location_preview",
            {
                "slot": self.slot.currentData(),
                "latitude": self.latitude.text(),
                "longitude": self.longitude.text(),
                "source": self.source,
            },
        )

    def confirm_preview(self, preview):
        if not self.armed:
            self.info.setText(
                "Preview checked. Arm SLM controls on SLM Screen, then preview again to send. No write sent."
            )
            return
        texts = [
            f"SLM: {preview['address']}\nSlot {preview['slot']}: {preview['name']}\nCurrent text: {preview['before']!r}\nReplace with: {preview['after']}\nSource: {preview['source']}\n\nThis overwrites this slot's text. It does not change native GPS or save the measurement. Continue?",
            "Confirm again: send this location text to the selected SLM metadata slot now? It can be saved with subsequent measurements when you confirm metadata on the SLM. A private local audit retains the old/new values.",
        ]
        for text in texts:
            if (
                QMessageBox.question(
                    self,
                    "Confirm SLM location text",
                    text,
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                    QMessageBox.StandardButton.No,
                )
                != QMessageBox.StandardButton.Yes
            ):
                self.info.setText("Location transfer cancelled; no write sent.")
                return
        self.command.emit("location_write", {"token": preview["token"], "confirmations": 2})

    def written(self, preview):
        self.info.setText(
            f"SLM slot {preview['slot']} text verified: {preview['after']}. Native GPS unchanged. Confirm metadata when saving the measurement on the SLM."
        )
