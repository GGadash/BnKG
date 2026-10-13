from unittest.mock import Mock

import pytest
from PySide6.QtWidgets import QApplication, QLabel, QPushButton

from bnkg.core.webxi import WebXiClient, WebXiError
from bnkg.ui.about import LINKS, AboutPage


def client():
    c = WebXiClient("fixture.local")
    c.actions = {"KeyUp", "KeyDown", "KeyLeft", "KeyRight"}
    c.armed = True
    c.navigation_ready = True
    c.get = Mock(return_value="Paused")
    reply = Mock(status_code=200)
    reply.__enter__ = Mock(return_value=reply)
    reply.__exit__ = Mock(return_value=False)
    c.session.put = Mock(return_value=reply)
    return c


@pytest.mark.parametrize("direction", ["up", "down", "left", "right"])
def test_screen_arrow_is_single_advertised_action_and_stays_armed(direction):
    c = client()
    c.navigate_measurement_screen(direction, screen_confirmed=True)
    assert c.session.put.call_count == 1
    assert c.session.put.call_args.kwargs["params"] == {"Action": "Key" + direction.title()}
    assert c.armed and not c.uncertain


@pytest.mark.parametrize("guard", ["disarmed", "unconfirmed", "unsupported", "uncertain", "state"])
def test_screen_arrow_guards_send_no_write(guard):
    c = client()
    if guard == "disarmed":
        c.armed = False
    elif guard == "unsupported":
        c.actions.clear()
    elif guard == "uncertain":
        c.uncertain = True
    elif guard == "state":
        c.get.return_value = "Stopped"
    with pytest.raises(PermissionError):
        c.navigate_measurement_screen("up", screen_confirmed=guard != "unconfirmed")
    c.session.put.assert_not_called()


def test_menu_and_measurement_commands_cannot_be_sent_as_arrows():
    c = client()
    for action in ["menu", "StartPause", "Stop", "up&Action=Stop", "Up"]:
        with pytest.raises(ValueError):
            c.navigate_measurement_screen(action, screen_confirmed=True)
    c.session.put.assert_not_called()


@pytest.mark.parametrize("failure", ["timeout", "status", "changed-state"])
def test_uncertain_arrow_disarms_and_never_retries(failure):
    c = client()
    if failure == "timeout":
        c.session.put.side_effect = TimeoutError()
    elif failure == "status":
        c.session.put.return_value.status_code = 500
    else:
        c.get.side_effect = ["Paused", "Running"]
    with pytest.raises(WebXiError, match="no retry"):
        c.navigate_measurement_screen("up", screen_confirmed=True)
    assert c.session.put.call_count == 1 and c.uncertain and not c.armed
    with pytest.raises(PermissionError):
        c.navigate_measurement_screen("up", screen_confirmed=True)
    assert c.session.put.call_count == 1


def test_all_about_links_are_clickable_and_copy_exact_url(qtbot):
    page = AboutPage("Double-check instrument readings.")
    qtbot.addWidget(page)
    for title, url in LINKS:
        button = next(
            b
            for b in page.findChildren(QPushButton)
            if b.accessibleName() == "Copy " + title + " link"
        )
        button.click()
        assert QApplication.clipboard().text() == url
        assert page.feedback.text() == "Link copied to clipboard"
        assert any(
            url in label.text() and label.openExternalLinks() for label in page.findChildren(QLabel)
        )
