"""Explicit local export preset preview/apply controls."""

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QComboBox,
    QGridLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QWidget,
)

from bnkg.core.export_profiles import BUILTINS, KEY, decode_profiles, encode_profiles, name_for


class ExportPresets(QWidget):
    apply_requested = Signal(object)

    def __init__(self, settings, current_profile):
        super().__init__()
        self.settings, self.current_profile = settings, current_profile
        self.error = ""
        try:
            self.saved = decode_profiles(settings.value(KEY, '{"version":1,"presets":[]}'))
        except ValueError as exc:
            self.saved, self.error = {}, str(exc)
        grid = QGridLayout(self)
        grid.setContentsMargins(0, 0, 0, 0)
        self.choices = QComboBox()
        self.choices.setMinimumContentsLength(8)
        self.choices.setSizeAdjustPolicy(
            QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon
        )
        self.apply = QPushButton("Apply export preset")
        self.apply.clicked.connect(lambda: self.apply_requested.emit(self.choices.currentData()[2]))
        grid.addWidget(self.choices, 0, 0)
        grid.addWidget(self.apply, 0, 1)
        self.preview = QLabel()
        self.preview.setWordWrap(True)
        self.preview.setTextFormat(Qt.TextFormat.PlainText)
        grid.addWidget(self.preview, 1, 0, 1, 2)
        self.name = QLineEdit()
        self.name.setMaxLength(60)
        self.name.setPlaceholderText("Name for current export options")
        self.save = QPushButton("Save new export preset")
        self.save.clicked.connect(self.save_current)
        grid.addWidget(self.name, 2, 0)
        grid.addWidget(self.save, 2, 1)
        self.delete = QPushButton("Delete saved preset")
        self.delete.clicked.connect(self.delete_current)
        grid.addWidget(self.delete, 3, 0, 1, 2)
        self.status = QLabel(
            self.error
            or "Local presets contain options only. Choosing one does not apply it or start an export."
        )
        self.status.setWordWrap(True)
        self.status.setTextFormat(Qt.TextFormat.PlainText)
        grid.addWidget(self.status, 4, 0, 1, 2)
        self.choices.currentIndexChanged.connect(self.show_preview)
        self.refresh()

    def refresh(self, selected=None):
        self.choices.blockSignals(True)
        self.choices.clear()
        for name, value in BUILTINS.items():
            self.choices.addItem(name, (False, name, value))
        for name, value in self.saved.items():
            self.choices.addItem("Saved · " + name, (True, name, value))
        if selected in self.saved:
            self.choices.setCurrentIndex(len(BUILTINS) + list(self.saved).index(selected))
        self.choices.blockSignals(False)
        self.show_preview()

    def show_preview(self, *_):
        saved, _, value = self.choices.currentData()
        self.preview.setText(
            f"Preset preview · {value.format_name.upper()} · spectra {'on' if value.include_spectra else 'off'} · raw {'on' if value.include_raw else 'off'}\n"
            + ", ".join(value.parameter_ids)
        )
        self.delete.setEnabled(saved and not self.error)
        self.save.setEnabled(not self.error)

    def store(self, saved):
        if self.error:
            return False
        try:
            encoded = encode_profiles(saved)
        except ValueError as exc:
            self.status.setText(str(exc))
            return False
        self.settings.setValue(KEY, encoded)
        self.settings.sync()
        self.saved = saved
        self.status.setText(
            "Local export presets saved."
            if self.settings.status() == self.settings.Status.NoError
            else "Options changed in memory, but preferences could not be saved to disk."
        )
        return True

    def save_current(self):
        try:
            name = name_for(self.name.text())
            if name.casefold() in {key.casefold() for key in self.saved}:
                raise ValueError(
                    "That name already exists. Use a new name; presets are not overwritten."
                )
            if len(self.saved) >= 20:
                raise ValueError("Up to 20 export presets are supported.")
            value = self.current_profile()
        except ValueError as exc:
            self.status.setText(str(exc))
            return
        if self.store({**self.saved, name: value}):
            self.refresh(name)
            self.name.clear()

    def delete_current(self):
        saved, name, _ = self.choices.currentData()
        if (
            saved
            and not self.error
            and QMessageBox.question(
                self,
                "Delete export preset",
                f"Delete '{name}'? Current export options stay unchanged.",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            == QMessageBox.StandardButton.Yes
        ):
            if self.store({key: value for key, value in self.saved.items() if key != name}):
                self.refresh()
