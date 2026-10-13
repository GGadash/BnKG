"""Local display preferences. Accept applies atomically; Cancel changes nothing."""

from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLabel,
    QSpinBox,
    QVBoxLayout,
)


class PreferencesDialog(QDialog):
    def __init__(self, settings, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Display preferences")
        layout = QVBoxLayout(self)
        note = QLabel("Local display preferences only. Instrument settings are unchanged.")
        note.setWordWrap(True)
        layout.addWidget(note)
        form = QFormLayout()
        self.font_size = QSpinBox()
        self.font_size.setRange(18, 40)
        self.font_size.setSuffix(" pt")
        self.font_size.setValue(settings.value("reading_font_size", 28, type=int))
        form.addRow("Reading size", self.font_size)
        self.density = QComboBox()
        self.density.addItems(["Comfortable", "Compact"])
        self.density.setCurrentText(settings.value("tile_density", "Comfortable"))
        form.addRow("Dashboard density", self.density)
        self.meter = QCheckBox("Show current LAF level bar")
        self.meter.setChecked(settings.value("dashboard_meter", True, type=bool))
        form.addRow(self.meter)
        self.meter_range = QComboBox()
        self.meter_range.addItems(["20–140 dB", "20–90 dB"])
        self.meter_range.setCurrentText(settings.value("dashboard_range", "20–140 dB"))
        form.addRow("Level bar range", self.meter_range)
        self.spectrum = QCheckBox("Show current spectrum preview")
        self.spectrum.setChecked(settings.value("dashboard_spectrum", False, type=bool))
        form.addRow(self.spectrum)
        self.spectrum_range = QComboBox()
        self.spectrum_range.addItems(["Auto range", "20–90 dB", "20–140 dB"])
        self.spectrum_range.setCurrentText(settings.value("spectrum_range", "Auto range"))
        form.addRow("Frequency display range", self.spectrum_range)
        self.reset_colors = QCheckBox("Reset A/C/Z colors to theme defaults")
        form.addRow(self.reset_colors)
        layout.addLayout(form)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def save(self, settings):
        for key, value in {
            "reading_font_size": self.font_size.value(),
            "tile_density": self.density.currentText(),
            "dashboard_meter": self.meter.isChecked(),
            "dashboard_range": self.meter_range.currentText(),
            "dashboard_spectrum": self.spectrum.isChecked(),
            "spectrum_range": self.spectrum_range.currentText(),
        }.items():
            settings.setValue(key, value)
        if self.reset_colors.isChecked():
            for weight in "ACZ":
                settings.remove("spectrum_color_" + weight)
