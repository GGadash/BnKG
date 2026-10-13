import struct
from unittest.mock import MagicMock

import pytest

from bnkg.core.audio import AudioClient, audio_sequences
from bnkg.core.safety import classify


def test_audio_setting_and_critical_operations_fail_closed():
    c = AudioClient("fixture.local", MagicMock())
    for value, expected, confirmations in [(1, 0, 0), (2, 0, 2), (True, 0, 2)]:
        with pytest.raises(PermissionError):
            c.set_analysis_quality(value, expected=expected, confirmations=confirmations)
    c.get = MagicMock(return_value="Running")
    with pytest.raises(PermissionError):
        c.set_analysis_quality(1, expected=0, confirmations=2)
    c.session.put.assert_not_called()
    for name in (
        "Reset",
        "ResetToDefault",
        "calibration",
        "service",
        "format",
        "delete",
        "unknown",
    ):
        assert not classify(name).allowed


def test_audio_descriptor_and_stream_confirmation_gate():
    tree = {"SLM": {"Audio": {"157": {"Name": "Audio", "DataFormat": "Flac", "PeriodTime": 65536}}}}
    sequence = audio_sequences(tree)[0]
    assert sequence["id"] == 157 and sequence["format"] == "flac"
    c = AudioClient("fixture.local", MagicMock())
    with pytest.raises(PermissionError):
        c.open_audio(sequence)
    c.get = MagicMock(return_value={})
    with pytest.raises(PermissionError):
        c.open_audio(sequence, confirmed=True)
    c.session.post.assert_not_called()
    tree["SLM"]["Audio"]["157"]["Direction"] = "ToDevice"
    assert not audio_sequences(tree)


def test_audio_message_fragmentation_and_bounds():
    c = AudioClient("fixture.local", MagicMock())
    message = struct.pack("<HHHHIQI", 0x4B42, 16, 1, 1, 0, 123, 4) + b"data"
    c.audio_socket = MagicMock()
    c.audio_socket.recv.return_value = message
    raw, info = c.read_message(lambda: False)
    assert raw == message and info["device_time_raw"] == 123
    c.audio_socket.recv.return_value = struct.pack("<HHHHIQI", 0x4B42, 16, 1, 1, 0, 123, 1048577)
    with pytest.raises(ValueError, match="oversized"):
        c.read_message(lambda: False)
    with pytest.raises(InterruptedError):
        c.read_message(lambda: True)


def test_owned_stream_cleanup_rejects_another_client():
    c = AudioClient("fixture.local", MagicMock())
    c.stream_path = "/webxi/Streams/7"
    c._request_json = MagicMock(
        return_value={"7": {"Name": "Other app", "Direction": "FromDevice"}}
    )
    with pytest.raises(PermissionError):
        c.close_audio()
    c.session.delete.assert_not_called()


def test_flac_repack_preserves_samples_and_checks_timing(tmp_path):
    import hashlib
    import json

    from bnkg.core.audio_capture import crc, wrap_flac

    rows = []
    with (tmp_path / "original.webxi").open("wb") as output:
        for i in range(3):
            # Valid mono 24-bit, 4096-sample constant subframe; encoder resets numbering.
            header = bytes.fromhex("fff8c00c00")
            frame = header + bytes([crc(header, 8, 7)]) + b"\0" * 4
            frame += crc(frame, 16, 0x8005).to_bytes(2, "big")
            payload = struct.pack("<hbbhhi", 1, 2, 0, 1, 157, len(frame)) + frame
            raw = (
                struct.pack("<HHHHIQI", 0x4B42, 16, 1, 0, 0, i * 268435456, len(payload)) + payload
            )
            rows.append(
                {
                    "offset": output.tell(),
                    "bytes": len(raw),
                    "sha256": hashlib.sha256(raw).hexdigest(),
                    "type": 1,
                    "version": 0,
                    "device_time_raw": i * 268435456,
                }
            )
            output.write(raw)
    ledger = tmp_path / "messages.jsonl"
    ledger.write_text("\n".join(json.dumps(r) for r in rows))
    info = wrap_flac(tmp_path, 157, 32 << 24)
    assert info["sample_rate_hz"] == 65536 and info["samples"] == 12288
    assert (tmp_path / "audio.flac").read_bytes()[:4] == b"fLaC"
    rows[2]["device_time_raw"] += 1
    ledger.write_text("\n".join(json.dumps(r) for r in rows))
    with pytest.raises(ValueError, match="Inconsistent"):
        wrap_flac(tmp_path, 157, 32 << 24)


def test_ambiguous_enable_still_inspects_and_restores(tmp_path, monkeypatch):
    import bnkg.core.audio_capture as module
    from bnkg.core.webxi import SETUP

    preview = {"state": "Activated", "setup": {"AudioRecordingAnalysisQuality": 0}, "sequences": []}
    first, restore = MagicMock(), MagicMock()
    first.inspect_audio.return_value = preview
    first.set_analysis_quality.side_effect = RuntimeError("Lost PUT acknowledgement")
    restore.get.side_effect = lambda path, **kwargs: (
        {"AudioRecordingAnalysisQuality": 1 if restore.set_analysis_quality.call_count == 0 else 0}
        if path == SETUP
        else "Activated"
    )
    monkeypatch.setattr(module, "AudioClient", MagicMock(side_effect=[first, restore]))
    _, result = module.capture_audio(
        {},
        tmp_path,
        preview,
        temporary_analysis=True,
        seconds=1,
        cancelled=lambda: False,
        progress=lambda _: None,
    )
    assert result["status"] == "incomplete" and result["setting_restored"]
    restore.set_analysis_quality.assert_called_once_with(0, expected=1, confirmations=2)
    first.open_audio.assert_not_called()


def test_audio_ui_decline_never_launches_capture(qtbot, tmp_path, monkeypatch):
    from PySide6.QtWidgets import QMessageBox

    from bnkg.ui.audio import AudioPanel

    panel = AudioPanel(tmp_path)
    qtbot.addWidget(panel)
    panel.set_connection({"address": "fixture.local"})
    panel.preview = {
        "state": "Activated",
        "setup": {"AudioRecordingAnalysisQuality": 0},
        "sequences": [],
    }
    panel.launch = MagicMock()
    monkeypatch.setattr(QMessageBox, "question", lambda *a: QMessageBox.StandardButton.No)
    panel.start_audio()
    panel.launch.assert_not_called()
    panel.set_connection(None)
    assert not panel.start_button.isEnabled()


def test_unknown_created_stream_is_not_claimed_closed():
    c = AudioClient("fixture.local", MagicMock())
    c.creation_pending = True
    with pytest.raises(RuntimeError, match="outcome uncertain"):
        c.close_audio()
    c.session.delete.assert_not_called()
