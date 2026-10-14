"""Require explicit first-use agreement before creating any acquisition worker."""

from pathlib import Path

from PySide6.QtCore import QStandardPaths
from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QMessageBox,
    QTextBrowser,
    QVBoxLayout,
)

from bnkg.core.disclaimer import DISCLAIMER, agreement_accepted, save_acceptance


def application_data_dir(explicit: Path | None) -> Path:
    if explicit is not None:
        return explicit
    directory = Path(
        QStandardPaths.writableLocation(QStandardPaths.StandardLocation.AppLocalDataLocation)
    )
    legacy = directory.parent / "HBKG"
    return legacy if not directory.exists() and legacy.is_dir() else directory


class UsageAgreement(QDialog):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("B&KG — first-use agreement")
        self.resize(680, 550)
        layout = QVBoxLayout(self)
        text = QTextBrowser()
        text.setPlainText(DISCLAIMER)
        layout.addWidget(text)
        self.confirm = QCheckBox(
            "I have read and understood this information and agree to use B&KG at my own risk."
        )
        layout.addWidget(self.confirm)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        self.continue_button = buttons.button(QDialogButtonBox.StandardButton.Ok)
        self.continue_button.setText("Agree and continue")
        self.continue_button.setEnabled(False)
        buttons.button(QDialogButtonBox.StandardButton.Cancel).setText("Decline and exit")
        self.confirm.toggled.connect(self.continue_button.setEnabled)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def accept(self):
        if self.confirm.isChecked():
            super().accept()


def ensure_agreement(directory: Path) -> bool:
    if agreement_accepted(directory):
        return True
    dialog = UsageAgreement()
    if dialog.exec() != QDialog.DialogCode.Accepted:
        return False
    try:
        save_acceptance(directory)
    except OSError:
        QMessageBox.critical(
            dialog,
            "Cannot save agreement",
            "The agreement could not be saved. Choose a writable data folder and restart. The app will close without connecting to an instrument.",
        )
        return False
    return True
