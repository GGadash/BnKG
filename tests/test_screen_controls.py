import time

import pytest
from PySide6.QtCore import QPoint, Qt
from PySide6.QtWidgets import QLabel, QMessageBox, QVBoxLayout, QWidget
from test_release import client
from test_stage5 import png

from bnkg.ui.components import ArmControlsCheckBox, ScreenPane
from bnkg.ui.window import MainWindow
from bnkg.ui.worker import AcquisitionWorker


def test_fit_uses_both_axes_with_long_controls_and_pixel_default(qtbot):
    controls = QWidget()
    layout = QVBoxLayout(controls)
    for i in range(80):
        layout.addWidget(QLabel("Control " + str(i)))
    view = ScreenPane(controls)
    qtbot.addWidget(view)
    assert view.zoom.currentData() == 2
    assert view.rendering.currentData() == "pixel"
    view.set_image(png())
    view.zoom.setCurrentIndex(view.zoom.findData(0))
    view.show()
    for width, height in [(1000, 480), (700, 800), (480, 620)]:
        view.resize(width, height)
        qtbot.wait(30)
        rendered, area = view.image.pixmap().size(), view.viewport.viewport().size()
        assert rendered.width() <= area.width() and rendered.height() <= area.height()
        assert view.image.isVisible()
        assert view.controls.verticalScrollBar().maximum() > 0
        assert view.viewport.verticalScrollBar().maximum() == 0
        assert view.viewport.horizontalScrollBar().maximum() == 0
    view.zoom.setCurrentIndex(view.zoom.findData(4))
    assert view.image.pixmap().width() == 964
    for method in ("sharp", "smooth", "pixel"):
        view.rendering.setCurrentIndex(view.rendering.findData(method))
        assert view.transformed_pixmap().size() == view.pixmap.size() * 4


def test_arm_whole_area_is_clickable_and_updates_status(qtbot):
    box = ArmControlsCheckBox()
    qtbot.addWidget(box)
    box.resize(500, 64)
    box.show()
    qtbot.mouseClick(box, Qt.MouseButton.LeftButton, pos=QPoint(485, 45))
    assert box.isChecked() and "ARMED" in box.text()
    qtbot.mouseClick(box, Qt.MouseButton.LeftButton, pos=QPoint(485, 45))
    assert not box.isChecked() and "OFF" in box.text()


def test_session_keys_menu_lock_and_no_hidden_setting_actions(qtbot):
    meter = client()
    meter.actions.add("KeyMenu")
    worker = AcquisitionWorker()
    worker.device = meter
    worker.screen_received, worker.screen_digest = time.monotonic(), "frame"
    worker.command(
        "screen_context", {"confirmed": True, "digest": "frame", "confirmed_at": time.monotonic()}
    )
    for direction in ("up", "down", "left", "right"):
        worker.command("screen_arrow", {"direction": direction, "confirmed_at": time.monotonic()})
        assert meter.armed and meter.navigation_ready
    worker.command("screen_menu", {"confirmed_at": time.monotonic()})
    assert meter.armed and not meter.navigation_ready
    assert meter.session.put.call_count == 5
    assert meter.session.put.call_args.kwargs["params"]["Action"] == "KeyMenu"
    worker.command("screen_arrow", {"direction": "down", "confirmed_at": time.monotonic()})
    worker.command("screen_menu", {"confirmed_at": time.monotonic()})
    assert meter.session.put.call_count == 5
    worker.command("arm", False)
    assert not meter.armed and not meter.navigation_ready


def test_measurement_buttons_have_no_dialog_and_menu_locks_ui(qtbot, tmp_path, monkeypatch):
    window = MainWindow(data_dir=tmp_path)
    qtbot.addWidget(window)
    window.command_requested.disconnect(window.worker.command)
    sent = []
    window.command_requested.connect(lambda *args: sent.append(args))
    monkeypatch.setattr(
        QMessageBox, "question", lambda *args: pytest.fail("Unexpected repeated confirmation")
    )
    try:
        window.source_mode = "instrument"
        actions = {"StartPause", "Stop", "KeyMenu", "KeyUp", "KeyDown", "KeyLeft", "KeyRight"}
        window.receive_controls(True, actions)
        window.slm_start.click()
        assert sent[-1] == ("slm_action", ("StartPause", 0))
        window.receive_controls(True, actions)
        window.slm_stop.click()
        assert sent[-1] == ("slm_action", ("Stop", 0))
        window.receive_controls(True, actions)
        window.slm_screen.set_image(png())
        window.slm_screen.set_status("Live SLM display")
        window.receive_keypad_state(True)
        window.screen_arrows["up"].click()
        assert sent[-1][0] == "screen_arrow"
        window.receive_controls(True, actions)
        window.screen_menu.click()
        assert sent[-1][0] == "screen_menu"
        assert not window.screen_context.isChecked()
        assert not window.screen_menu.isEnabled()
        window.receive_controls(False, [])
        assert not window.arm_controls.isChecked()
    finally:
        window.close()
        qtbot.waitUntil(lambda: window.thread_finished)
