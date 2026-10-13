import json
import struct

import pytest

from bnkg.core.bkc import read_bkc
from bnkg.core.media_export import sync_plan


def bkc_fixture():
    xml = b'<Storage Version="2"><ClockSource><Table><Sequence Name="Example" DataType="Int16" Id="6"><File>.Part2</File><IndexMapping><Type>Explicit</Type></IndexMapping></Sequence></Table></ClockSource></Storage>'
    table = struct.pack("<8I", 0x1A2B3C4D, 0, 0, 0, 0, 0, 1, 1) + struct.pack(
        "<IQIIh", 6, 0, 2, 1, 1234
    )
    name = ".Part2".encode("utf-16le")
    header_size = 12 + 18 + 18 + len(name)
    return (
        struct.pack("<IIIHQQH", 0x72E176FB, 0, 2, 0, header_size, len(xml), 6)
        + name
        + struct.pack("<QQ", header_size + len(xml), len(table))
        + xml
        + table
    )


def test_bkc_raw_decode_and_refuse_uncertain_layouts(tmp_path):
    path = tmp_path / "fixture.bkc"
    original = bkc_fixture()
    path.write_bytes(original)
    decoded = read_bkc(path)
    assert decoded["raw_rows"][0]["raw_values"] == [1234]
    assert "scale/units" in decoded["raw_rows"][0]["interpretation"]
    assert path.read_bytes() == original
    for broken in (original[:-1], original[:4] + struct.pack("<I", 9) + original[8:]):
        path.write_bytes(broken)
        with pytest.raises(ValueError):
            read_bkc(path)
    malicious = original.replace(b'<Storage Version="2">', b'<!DOCTYPE x><Storage Version="2">')
    # Unmodified directory also refuses trailing/out-of-bounds content.
    path.write_bytes(malicious)
    with pytest.raises(ValueError):
        read_bkc(path)


def test_bkc_xml_entities_rejected():
    from bnkg.core.bkc import xml_root

    with pytest.raises(ValueError, match="entities"):
        xml_root(b'<!DOCTYPE x [<!ENTITY value "test">]><x>&value;</x>')


def test_sync_plan_uses_shared_session_and_signed_offset(tmp_path):
    a = tmp_path / "audio"
    v = tmp_path / "video"
    a.mkdir()
    v.mkdir()
    am = {"status": "complete", "clock_id": "clock", "sync_id": "pair", "audio": {"duration_s": 4}}
    vm = {"status": "complete", "clock_id": "clock", "sync_id": "pair", "duration_s": 8}
    (a / "audio.json").write_text(json.dumps(am))
    (v / "recording.json").write_text(json.dumps(vm))
    (a / "messages.jsonl").write_text(json.dumps({"pc_monotonic": 102}))
    (v / "frames.jsonl").write_text(json.dumps({"monotonic": 100}))
    assert sync_plan(a, v)["offset_s"] == 2
    assert sync_plan(a, v, -3000)["offset_s"] == -1
    with pytest.raises(ValueError, match="overlapping"):
        sync_plan(a, v, 12000)
    vm["clock_id"] = "another boot"
    (v / "recording.json").write_text(json.dumps(vm))
    with pytest.raises(ValueError, match="same paired"):
        sync_plan(a, v)


def test_media_ui_never_autoplays_and_shutdown_stops(qtbot, tmp_path):
    from PySide6.QtCore import QSettings
    from PySide6.QtMultimedia import QMediaPlayer

    from bnkg.ui.media import MediaPanel
    from bnkg.ui.recording import RecordingPanel

    panel = MediaPanel(
        RecordingPanel(
            QSettings(str(tmp_path / "prefs.ini"), QSettings.Format.IniFormat), tmp_path
        ),
        tmp_path,
    )
    qtbot.addWidget(panel)
    assert panel.player.playbackState() == QMediaPlayer.PlaybackState.StoppedState
    assert panel.output.volume() == pytest.approx(0.25)
    assert not panel.aac.isEnabled()
    panel.shutdown()
    assert panel.player.source().isEmpty()


def test_bkc_worker_view_no_acoustic_conversion(qtbot, tmp_path):
    from bnkg.ui.bkc import BkcPanel

    path = tmp_path / "test.bkc"
    path.write_bytes(bkc_fixture())
    panel = BkcPanel(tmp_path)
    qtbot.addWidget(panel)
    panel.open_path(path)
    qtbot.waitUntil(lambda: panel.job is None)
    assert panel.table.item(0, 4).text() == "[1234] (raw)"
    assert "awaiting independent comparison" in panel.status.text()


def test_validated_profile_keeps_totals_negative_bands_and_missing_c():
    from bnkg.core.bkc import decode_total

    result = {
        "file": "synthetic.total.bkc",
        "sha256": "synthetic",
        "start_time_text": "2026-01-01T00:00:00+00:00",
        "context": {
            "instrument_type": "2255",
            "firmware": "1.3.0.478",
            "time_powers": [32, 0, 0, 0],
            "primary_sequence_id": "140",
        },
        "constants": [
            {"name": name, "data_type": "BKTimeSpan", "raw_value": str(4 * 2**32)}
            for name in ("ElapsedTime", "StopTime")
        ]
        + [{"name": "LatchedOverload", "data_type": "DataQuality", "raw_value": "0"}],
        "raw_rows": [],
    }
    for name, weight, values, function in [
        ("LAeq", "A", [5500], "BroadbandLeq"),
        ("CPBLZeq", "Z", [4000] * 36, "OctaveLeq"),
        ("CPBLAeq2nd", "A", [-1000] * 36, "OctaveLeq"),
    ]:
        axis = (
            "<DataAxis><Type>Cpb</Type><Length>36</Length><CpbFirstBand>8</CpbFirstBand><CpbNumberFractions>3</CpbNumberFractions></DataAxis>"
            if len(values) > 1
            else ""
        )
        result["raw_rows"].append(
            {
                "name": name,
                "data_type": "Int16",
                "function": function,
                "weighting": weight,
                "time_weighting": None,
                "raw_values": values,
                "descriptor_xml": f"<Sequence><General><Description>{name}</Description></General>{axis}</Sequence>",
            }
        )
    decoded = decode_total(result)
    assert dict(decoded["frame"].broadband) == {"LAeq": 55}
    assert decoded["frame"].series[1].values[0] == -10
    assert all(
        s.meaning.kind == "total" and s.meaning.period_ms is None and s.origin == "instrument"
        for s in decoded["frame"].series
    )
    assert not any(s.meaning.weighting == "C" for s in decoded["frame"].series)
    result["context"]["firmware"] = "unverified"
    assert decode_total(result) is None


def test_audio_startup_epoch_change_retains_raw_and_marks_omission(tmp_path):
    import hashlib

    from bnkg.core.audio_capture import crc, wrap_flac

    rows = []
    all_bytes = b""
    for i in range(4):
        header = bytes.fromhex("fff8c00c00")
        frame = header + bytes([crc(header, 8, 7)]) + b"\0" * 4
        frame += crc(frame, 16, 0x8005).to_bytes(2, "big")
        stamp = 1700000000 * 2**32 if i == 0 else i * 268435456
        payload = struct.pack("<hbbhhi", 1, 2, 0, 1, 157, len(frame)) + frame
        raw = struct.pack("<HHHHIQI", 0x4B42, 16, 1, 0, 0, stamp, len(payload)) + payload
        rows.append(
            {
                "offset": len(all_bytes),
                "bytes": len(raw),
                "sha256": hashlib.sha256(raw).hexdigest(),
                "type": 1,
                "version": 0,
                "device_time_raw": stamp,
                "pc_monotonic": 100 + i * 0.0625,
            }
        )
        all_bytes += raw
    (tmp_path / "original.webxi").write_bytes(all_bytes)
    (tmp_path / "messages.jsonl").write_text("\n".join(json.dumps(r) for r in rows))
    result = wrap_flac(tmp_path, 157, 32 << 24)
    assert result["startup_frames_omitted"] == 1 and result["frames"] == 3
    assert result["first_pc_monotonic"] == 100.0625
    assert (tmp_path / "original.webxi").read_bytes() == all_bytes
