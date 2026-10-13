"""Searchable local Dashboard visibility catalogue; no acquisition or device calls."""

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QGridLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from bnkg.core.parameter_views import (
    BUILTINS,
    GROUPS,
    PRESET_KEY,
    group_for,
    preset_name,
    read_presets,
    visible_ids,
    write_presets,
)
from bnkg.core.parameters import PARAMETERS
from bnkg.ui.presentation import parameter_scope


def label(text):
    item = QLabel(text)
    item.setWordWrap(True)
    item.setTextFormat(Qt.TextFormat.PlainText)
    return item


class ParameterCatalogue(QWidget):
    selection_changed = Signal()

    def __init__(self, settings, selected):
        super().__init__()
        self.settings = settings
        self.checks, self.rows, self.search_text = {}, {}, {}
        self.previous = None
        self.storage_error = ""
        try:
            self.presets = read_presets(settings.value(PRESET_KEY, '{"version":1,"presets":[]}'))
        except ValueError as exc:
            self.presets = {}
            self.storage_error = str(exc)
        layout = QVBoxLayout(self)
        layout.addWidget(
            label(
                "Choose Dashboard values · Local display only. Availability depends on the SLM configuration; selecting a value does not enable it on the instrument. Filters preserve selections. Capture, logging, charts and exports keep their own settings."
            )
        )
        controls = QGridLayout()
        self.search = QLineEdit()
        self.search.setMaxLength(120)
        self.search.setPlaceholderText("Search ID, description, measurement scope or formula")
        self.search.setAccessibleName("Search parameters")
        self.group = QComboBox()
        self.group.addItems(("All groups",) + GROUPS)
        self.group.setMinimumContentsLength(6)
        self.group.setSizeAdjustPolicy(
            QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon
        )
        self.selected_only = QCheckBox("Selected only")
        self.select_shown = QPushButton("Select shown")
        self.clear_shown = QPushButton("Clear shown")
        self.undo = QPushButton("Undo selection change")
        self.undo.clicked.connect(self.undo_selection)
        self.select_shown.clicked.connect(lambda: self.change_shown(True))
        self.clear_shown.clicked.connect(lambda: self.change_shown(False))
        controls.addWidget(self.search, 0, 0, 1, 2)
        controls.addWidget(self.group, 1, 0)
        controls.addWidget(self.selected_only, 1, 1)
        controls.addWidget(self.select_shown, 2, 0)
        controls.addWidget(self.clear_shown, 2, 1)
        self.preset = QComboBox()
        self.preset.setMinimumContentsLength(6)
        self.preset.setSizeAdjustPolicy(
            QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon
        )
        self.apply = QPushButton("Apply preset")
        self.apply.clicked.connect(self.apply_preset)
        controls.addWidget(self.preset, 3, 0)
        controls.addWidget(self.apply, 3, 1)
        layout.addLayout(controls)
        self.preview = label("")
        layout.addWidget(self.preview)
        self.count = label("")
        layout.addWidget(self.count)
        content = QWidget()
        rows_layout = QVBoxLayout(content)
        rows_layout.setContentsMargins(0, 0, 0, 0)
        selected = visible_ids(selected)
        for p in PARAMETERS:
            row = QWidget()
            row_layout = QVBoxLayout(row)
            row_layout.setContentsMargins(6, 5, 6, 8)
            row_layout.setSpacing(3)
            check = QCheckBox(p.label + (" · Calculated" if p.formula else ""))
            check.setChecked(p.id in selected)
            check.setEnabled(not p.formula)
            scope = (
                "Calculated difference; common measurement period required"
                if p.formula
                else parameter_scope(p.id)
            )
            detail = f"{group_for(p)} · {scope} · {p.unit}\n{p.description}"
            detail += (
                "\nFormula: "
                + p.formula
                + ". Shown separately on Dashboard; not a direct SLM output."
                if p.formula
                else "\nDirect SLM output when available; configured basis must be checked on the instrument."
            )
            check.setToolTip(detail)
            row_layout.addWidget(check)
            row_layout.addWidget(label(detail))
            self.checks[p.id], self.rows[p.id] = check, row
            self.search_text[p.id] = (p.id + " " + p.label + " " + detail).casefold()
            check.toggled.connect(self.manual_change)
            rows_layout.addWidget(row)
        rows_layout.addStretch()
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setWidget(content)
        layout.addWidget(self.scroll, 1)
        saved = QGridLayout()
        self.name = QLineEdit()
        self.name.setMaxLength(60)
        self.name.setPlaceholderText("Name for current selection")
        self.save = QPushButton("Save new preset")
        self.save.clicked.connect(self.save_preset)
        self.delete = QPushButton("Delete saved preset")
        self.delete.clicked.connect(self.delete_preset)
        saved.addWidget(self.name, 0, 0)
        saved.addWidget(self.save, 0, 1)
        saved.addWidget(self.delete, 1, 0)
        saved.addWidget(self.undo, 1, 1)
        layout.addLayout(saved)
        self.status = label(
            self.storage_error
            or "Presets change the entire Dashboard selection, including rows hidden by filters. No instrument setup is stored or applied."
        )
        layout.addWidget(self.status)
        self.search.textChanged.connect(self.filter_rows)
        self.group.currentTextChanged.connect(self.filter_rows)
        self.selected_only.toggled.connect(self.filter_rows)
        self.preset.currentIndexChanged.connect(self.preview_preset)
        self.refresh_presets()
        self.filter_rows()

    def selection(self):
        return tuple(
            key for key, check in self.checks.items() if check.isChecked() and check.isEnabled()
        )

    def filter_rows(self, *_):
        tokens = self.search.text().casefold().split()
        shown = []
        for p in PARAMETERS:
            match = (
                all(token in self.search_text[p.id] for token in tokens)
                and (self.group.currentIndex() == 0 or self.group.currentText() == group_for(p))
                and (not self.selected_only.isChecked() or self.checks[p.id].isChecked())
            )
            self.rows[p.id].setVisible(match)
            if match:
                shown.append(p.id)
        self.shown = tuple(shown)
        selected = self.selection()
        hidden = len(set(selected) - set(shown))
        self.count.setText(
            f"{len(shown)} of {len(PARAMETERS)} parameters shown · {len(selected)} selected · {hidden} selected outside this filter"
            + (". No matches; clear search or change the group." if not shown else "")
        )
        available = any(self.checks[key].isEnabled() for key in shown)
        self.select_shown.setEnabled(available)
        self.clear_shown.setEnabled(available)
        self.undo.setEnabled(self.previous is not None)

    def manual_change(self, *_):
        self.previous = None
        self.filter_rows()
        self.selection_changed.emit()

    def set_selection(self, ids):
        ids = visible_ids(ids)
        before = self.selection()
        if before == ids:
            return
        self.previous = before
        for key, check in self.checks.items():
            check.blockSignals(True)
            check.setChecked(key in ids)
            check.blockSignals(False)
        self.filter_rows()
        self.selection_changed.emit()

    def change_shown(self, enabled):
        ids = set(self.selection())
        shown = {key for key in self.shown if self.checks[key].isEnabled()}
        self.set_selection(tuple(ids | shown if enabled else ids - shown))

    def undo_selection(self):
        if self.previous is not None:
            previous = self.previous
            self.set_selection(previous)
            self.previous = None
            self.filter_rows()

    def refresh_presets(self, selected=None):
        self.preset.blockSignals(True)
        self.preset.clear()
        for name, ids in BUILTINS.items():
            self.preset.addItem(name, (False, name, ids))
        for name, ids in self.presets.items():
            self.preset.addItem("Saved · " + name, (True, name, ids))
        if selected in self.presets:
            self.preset.setCurrentIndex(len(BUILTINS) + list(self.presets).index(selected))
        self.preset.blockSignals(False)
        self.preview_preset()

    def preview_preset(self, *_):
        saved, _, ids = self.preset.currentData()
        self.preview.setText(
            "Preset preview: "
            + (", ".join(ids) if ids else "no Dashboard scalar tiles")
            + ". Apply replaces the full selection; merely choosing a preset changes nothing."
        )
        self.delete.setEnabled(saved and not self.storage_error)
        self.save.setEnabled(not self.storage_error)

    def apply_preset(self):
        self.set_selection(self.preset.currentData()[2])

    def store(self, presets):
        if self.storage_error:
            return False
        try:
            encoded = write_presets(presets)
        except ValueError as exc:
            self.status.setText(str(exc))
            return False
        self.settings.setValue(PRESET_KEY, encoded)
        self.settings.sync()
        self.presets = presets
        if self.settings.status() != self.settings.Status.NoError:
            self.status.setText(
                "Preset changed in memory, but preferences could not be saved to disk."
            )
        else:
            self.status.setText("Local visibility presets saved. No instrument settings changed.")
        return True

    def save_preset(self):
        try:
            name = preset_name(self.name.text())
            if name.casefold() in {key.casefold() for key in self.presets}:
                raise ValueError(
                    "That name already exists. Use a new name; saved presets are not overwritten."
                )
            if len(self.presets) >= 20:
                raise ValueError(
                    "Up to 20 local presets are supported. Delete an unused preset first."
                )
        except ValueError as exc:
            self.status.setText(str(exc))
            return
        if self.store({**self.presets, name: self.selection()}):
            self.refresh_presets(name)
            self.name.clear()

    def delete_preset(self):
        saved, name, _ = self.preset.currentData()
        if not saved or self.storage_error:
            return
        if (
            QMessageBox.question(
                self,
                "Delete local preset",
                f"Delete saved visibility preset '{name}'? Current Dashboard selection will stay unchanged.",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            != QMessageBox.StandardButton.Yes
        ):
            return
        if self.store({key: ids for key, ids in self.presets.items() if key != name}):
            self.refresh_presets()
