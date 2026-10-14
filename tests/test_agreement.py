import json

from PySide6.QtWidgets import QDialog

from bnkg.core.disclaimer import AGREEMENT_REVISION, agreement_accepted, save_acceptance
from bnkg.ui.agreement import UsageAgreement, ensure_agreement


def test_acceptance_revision_and_corrupt_record(tmp_path):
    assert not agreement_accepted(tmp_path)
    save_acceptance(tmp_path)
    assert agreement_accepted(tmp_path)
    path = tmp_path / "usage-agreement.json"
    record = json.loads(path.read_text())
    assert record["revision"] == AGREEMENT_REVISION and record["accepted_utc"]
    record["revision"] = "old"
    path.write_text(json.dumps(record))
    assert not agreement_accepted(tmp_path)
    path.write_text("broken")
    assert not agreement_accepted(tmp_path)


def test_explicit_checkbox_required_and_decline_saves_nothing(qtbot, tmp_path, monkeypatch):
    dialog = UsageAgreement()
    qtbot.addWidget(dialog)
    assert not dialog.continue_button.isEnabled()
    dialog.accept()
    assert dialog.result() == QDialog.DialogCode.Rejected
    dialog.confirm.setChecked(True)
    assert dialog.continue_button.isEnabled()
    dialog.accept()
    assert dialog.result() == QDialog.DialogCode.Accepted
    monkeypatch.setattr(UsageAgreement, "exec", lambda self: QDialog.DialogCode.Rejected)
    assert not ensure_agreement(tmp_path)
    assert not list(tmp_path.iterdir())


def test_agreed_once_then_not_prompted(qtbot, tmp_path, monkeypatch):
    calls = []
    monkeypatch.setattr(
        UsageAgreement, "exec", lambda self: calls.append(True) or QDialog.DialogCode.Accepted
    )
    assert ensure_agreement(tmp_path) and ensure_agreement(tmp_path)
    assert len(calls) == 1


def test_save_failure_does_not_allow_startup(qtbot, tmp_path, monkeypatch):
    from bnkg.ui import agreement

    monkeypatch.setattr(UsageAgreement, "exec", lambda self: QDialog.DialogCode.Accepted)

    def fail(_):
        raise OSError("read-only")

    monkeypatch.setattr(agreement, "save_acceptance", fail)
    monkeypatch.setattr(agreement.QMessageBox, "critical", lambda *args: None)
    assert not ensure_agreement(tmp_path)


def test_declined_launch_never_creates_main_window(qapp, tmp_path, monkeypatch):
    from bnkg import app as module

    monkeypatch.setattr(module.sys, "argv", ["BnKG", "--data-dir", str(tmp_path)])
    monkeypatch.setattr(module, "QApplication", lambda args: qapp)
    monkeypatch.setattr(module, "ensure_agreement", lambda directory: False)

    def forbidden(**kwargs):
        raise AssertionError("Acquisition window created before consent")

    monkeypatch.setattr(module, "MainWindow", forbidden)
    assert module.main() == 0
