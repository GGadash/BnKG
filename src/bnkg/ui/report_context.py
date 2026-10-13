"""Separate local report draft for future logs; no device commands."""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QFormLayout,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from bnkg.core.report_context import FIELDS, log_filename, validate_context


class ReportContextPanel(QWidget):
    def __init__(self, settings):
        super().__init__()
        self.settings = settings
        layout = QVBoxLayout(self)
        note = QLabel(
            "LOCAL REPORT DETAILS · User-entered, not SLM metadata. New local logs take a copy when logging starts. Changes apply to future logs only; nothing is sent to the instrument. Drafts are saved on this PC and may contain private information."
        )
        note.setWordWrap(True)
        layout.addWidget(note)
        form = QFormLayout()
        form.setRowWrapPolicy(QFormLayout.RowWrapPolicy.WrapLongRows)
        self.fields = {}
        for key, limit in FIELDS.items():
            edit = QPlainTextEdit() if key == "notes" else QLineEdit()
            edit.setAccessibleName("Local report " + key)
            if key == "notes":
                edit.setMaximumHeight(120)
                edit.setPlainText(str(settings.value("report_" + key, ""))[:limit])
            else:
                edit.setMaxLength(limit)
                edit.setText(str(settings.value("report_" + key, "")))
            self.fields[key] = edit
            form.addRow(key.title() + (" (2,000 characters)" if key == "notes" else ""), edit)
        layout.addLayout(form)
        self.naming = QComboBox()
        self.naming.addItems(["Timestamp only", "Project and site + timestamp"])
        self.naming.setCurrentIndex(int(settings.value("report_named", 0)) % 2)
        layout.addWidget(self.naming)
        self.preview = QLabel()
        self.preview.setWordWrap(True)
        self.preview.setTextFormat(Qt.TextFormat.PlainText)
        layout.addWidget(self.preview)
        for edit in self.fields.values():
            edit.textChanged.connect(self.refresh_preview)
        self.naming.currentIndexChanged.connect(self.refresh_preview)
        save = QPushButton("Save local draft")
        save.clicked.connect(self.save_draft)
        layout.addWidget(save)
        self.feedback = QLabel(
            "No draft is sent to the SLM. Notes are included in metadata-bearing exports, not flat CSV/TSV/TXT rows."
        )
        self.feedback.setWordWrap(True)
        self.feedback.setTextFormat(Qt.TextFormat.PlainText)
        layout.addWidget(self.feedback)
        layout.addStretch()
        self.refresh_preview()

    def values(self):
        return validate_context(
            {
                key: edit.toPlainText() if key == "notes" else edit.text()
                for key, edit in self.fields.items()
            }
        )

    def snapshot(self):
        values = self.values()
        for key, text in values.items():
            self.settings.setValue("report_" + key, text)
        self.settings.setValue("report_named", self.naming.currentIndex())
        return values

    def save_draft(self):
        try:
            self.snapshot()
            self.feedback.setText(
                "Local draft saved. Future logs capture these details; existing sessions are unchanged."
            )
        except ValueError as exc:
            self.feedback.setText(str(exc))

    def refresh_preview(self, *_):
        try:
            filename = log_filename(self.values(), bool(self.naming.currentIndex()))
            self.preview.setText(
                "New log filename example (UTC): "
                + filename
                + " · Actual timestamp is assigned when logging starts."
            )
        except ValueError as exc:
            self.preview.setText(str(exc))
