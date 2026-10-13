import json

import pytest
from PySide6.QtCore import QSettings
from PySide6.QtWidgets import QMessageBox

from bnkg.core.parameter_views import BUILTINS, PRESET_KEY, read_presets, visible_ids, write_presets
from bnkg.core.parameters import BY_ID, PARAMETERS
from bnkg.ui.parameters import ParameterCatalogue
from bnkg.ui.window import MainWindow


def settings(tmp_path):
    return QSettings(str(tmp_path / "preferences.ini"), QSettings.Format.IniFormat)


def test_filter_preserves_hidden_selection_and_bulk_undo(qtbot, tmp_path):
    panel = ParameterCatalogue(settings(tmp_path), ["LAF", "LAeq", "L90"])
    qtbot.addWidget(panel)
    changed = []
    panel.selection_changed.connect(lambda: changed.append(panel.selection()))
    panel.search.setText("current fast")
    assert set(panel.shown) == {"LAF", "LCF", "LZF"}
    assert set(panel.selection()) == {"LAF", "LAeq", "L90"} and not changed
    panel.clear_shown.click()
    assert set(panel.selection()) == {"LAeq", "L90"} and len(changed) == 1
    panel.undo.click()
    assert set(panel.selection()) == {"LAF", "LAeq", "L90"} and len(changed) == 2
    panel.group.setCurrentText("Calculated differences")
    panel.search.clear()
    assert len(panel.shown) == 2 and not panel.select_shown.isEnabled()
    assert all(not panel.checks[key].isEnabled() for key in panel.shown)
    assert "Formula:" in panel.checks["LCeq_minus_LAeq"].toolTip()
    panel.selected_only.setChecked(True)
    assert not panel.shown and "No matches" in panel.count.text()
    assert set(panel.selection()) == {"LAF", "LAeq", "L90"}


def test_preset_preview_explicit_apply_save_reload_and_delete(qtbot, tmp_path, monkeypatch):
    prefs = settings(tmp_path)
    panel = ParameterCatalogue(prefs, ["LAF"])
    qtbot.addWidget(panel)
    panel.preset.setCurrentText("Measurement equivalents")
    assert panel.selection() == ("LAF",)
    panel.search.setText("L90")  # Applying a preset explicitly includes hidden rows.
    panel.apply.click()
    assert panel.selection() == BUILTINS["Measurement equivalents"]
    assert all(not BY_ID[key].formula for key in panel.selection())
    panel.name.setText("Survey · total")
    panel.save.click()
    encoded = prefs.value(PRESET_KEY)
    panel.name.setText("survey · TOTAL")
    panel.save.click()
    assert "already exists" in panel.status.text() and prefs.value(PRESET_KEY) == encoded
    restored = ParameterCatalogue(settings(tmp_path), [])
    qtbot.addWidget(restored)
    assert restored.selection() == ()  # Loading a named preset never auto-applies it.
    restored.preset.setCurrentText("Saved · Survey · total")
    restored.apply.click()
    assert restored.selection() == panel.selection()
    monkeypatch.setattr(QMessageBox, "question", lambda *args: QMessageBox.StandardButton.Yes)
    restored.delete.click()
    assert not restored.presets and restored.selection() == panel.selection()
    assert read_presets(settings(tmp_path).value(PRESET_KEY)) == {}


@pytest.mark.parametrize(
    "payload",
    [
        '{"version":2,"presets":[]}',
        '{"version":true,"presets":[]}',
        '{"version":1,"presets":[{"name":"Custom","ids":["unknown"]}]}',
        '{"version":1,"presets":[{"name":"Custom","ids":["LCeq_minus_LAeq"]}]}',
        pytest.param("x" * 32769, id="oversized"),
    ],
)
def test_bad_preferences_retained_and_builtin_selection_still_works(qtbot, tmp_path, payload):
    prefs = settings(tmp_path)
    prefs.setValue(PRESET_KEY, payload)
    panel = ParameterCatalogue(prefs, ["LAF"])
    qtbot.addWidget(panel)
    assert panel.storage_error and not panel.save.isEnabled()
    panel.preset.setCurrentText("Current A / C / Z")
    panel.apply.click()
    assert panel.selection() == BUILTINS["Current A / C / Z"]
    assert prefs.value(PRESET_KEY) == payload


def test_serialization_limits_and_empty_selection():
    assert visible_ids("LAFeq") == ("LAFeq",)  # Do not select LAF by substring.
    assert visible_ids([]) == ()
    assert read_presets(write_presets({"Empty": (), "Current": ("LAF", "LZF")}))["Empty"] == ()
    for presets in (
        {f"Preset {i}": () for i in range(21)},
        {"X" * 61: ()},
        {"recommended": ()},
        {"One": ("LAF", "LAF")},
    ):
        with pytest.raises(ValueError):
            write_presets(presets)
    duplicate = {"version": 1, "presets": [{"name": "One", "ids": []}, {"name": "one", "ids": []}]}
    with pytest.raises(ValueError):
        read_presets(json.dumps(duplicate))


def test_main_window_legacy_selection_migration_and_no_device_commands(qtbot, tmp_path):
    prefs = settings(tmp_path)
    prefs.setValue("visible", [p.id for p in PARAMETERS[:9]])
    prefs.sync()
    window = MainWindow(data_dir=tmp_path)
    commands = []
    window.command_requested.connect(lambda *args: commands.append(args))
    try:
        panel = window.parameter_catalogue
        assert panel.checks is window.checks
        assert "LAF" in panel.selection()
        panel.search.setText("LZF")
        panel.select_shown.click()
        assert "LZF" in panel.selection()
        assert set(window.settings.value("visible")) == set(panel.selection())
        assert not window.tiles["LZF"].isHidden()
        assert window.tiles["LCeq_minus_LAeq"].isHidden()
        panel.set_selection(())
        assert window.settings.value("visible") == []
        assert not commands and not window.logging and not window.capturing
    finally:
        window.close()
        qtbot.waitUntil(lambda: window.thread_finished)
    reopened = MainWindow(data_dir=tmp_path)
    try:
        assert reopened.parameter_catalogue.selection() == ()
    finally:
        reopened.close()
        qtbot.waitUntil(lambda: reopened.thread_finished)
