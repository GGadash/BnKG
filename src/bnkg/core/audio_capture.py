"""Original instrument audio archive with explicit provenance and bounded capture."""

import hashlib
import json
import shutil
import struct
import time
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from bnkg.core.audio import AudioClient
from bnkg.core.capture_clock import CAPTURE_CLOCK_ID
from bnkg.core.webxi import SETUP, STATE


def flac_block(raw, sequence_id):
    """Accept the observed mono, fixed-block FLAC variant; retain all other raw data."""
    if len(raw) < 36:
        raise ValueError("Truncated audio block")
    blocks, fmt, reserved, count, seq, size = struct.unpack("<hbbhhi", raw[24:36])
    if (blocks, fmt, reserved, count, seq) != (1, 2, 0, 1, sequence_id) or size != len(raw) - 36:
        raise ValueError("Unsupported audio block layout; originals retained")
    frame = raw[36:]
    if not frame:
        return None
    if len(frame) < 8 or frame[:2] != b"\xff\xf8" or frame[3] != 12:
        raise ValueError("Unsupported FLAC channel/depth/block strategy; originals retained")
    code, rate = frame[2] >> 4, frame[2] & 15
    if not 8 <= code <= 15 or rate != 0:
        raise ValueError("Unsupported FLAC block/rate header; originals retained")
    samples = 256 << (code - 8)
    # UTF-8 coded unsigned frame number, not text. Bound it to the FLAC fixed-frame range.
    first = frame[4]
    if first < 128:
        number = first
    else:
        width = next((n for n in range(2, 7) if first >> (7 - n) == (1 << (n + 1)) - 2), None)
        if width is None or len(frame) < 5 + width:
            raise ValueError("Invalid FLAC frame number")
        number = first & ((1 << (7 - width)) - 1)
        for byte in frame[5 : 4 + width]:
            if byte & 192 != 128:
                raise ValueError("Invalid FLAC frame number")
            number = (number << 6) | (byte & 63)
    return frame, samples, number


def crc(data, bits, polynomial):
    value = 0
    for byte in data:
        value ^= byte << (bits - 8)
        for _ in range(8):
            value = ((value << 1) ^ (polynomial if value & (1 << (bits - 1)) else 0)) & (
                (1 << bits) - 1
            )
    return value


def renumber_frame(frame, number):
    # The instrument can reset FLAC frame numbers within a continuous Web-XI stream.
    # Validate original checksums, then replace only numbering and dependent checksums.
    first = frame[4]
    width = (
        1 if first < 128 else next(n for n in range(2, 7) if first >> (7 - n) == (1 << (n + 1)) - 2)
    )
    end = 4 + width
    if crc(frame[:end], 8, 7) != frame[end] or crc(frame[:-2], 16, 0x8005) != int.from_bytes(
        frame[-2:], "big"
    ):
        raise ValueError("FLAC frame checksum mismatch; originals retained")
    if number < 128:
        encoded = bytes([number])
    elif number < 2048:
        encoded = bytes([192 | (number >> 6), 128 | (number & 63)])
    elif number < 65536:
        encoded = bytes([224 | (number >> 12), 128 | ((number >> 6) & 63), 128 | (number & 63)])
    else:
        raise ValueError("Audio frame-count limit exceeded")
    header = frame[:4] + encoded
    body = header + bytes([crc(header, 8, 7)]) + frame[end + 1 : -2]
    return body + crc(body, 16, 0x8005).to_bytes(2, "big")


def ticks_per_second(family):
    if type(family) is not int or not 0 <= family <= 0xFFFFFFFF:
        raise ValueError("Unknown device time family")
    powers = [(family >> shift) & 255 for shift in (24, 16, 8, 0)]
    if any(p > 40 for p in powers):
        raise ValueError("Unsupported device time family")
    return 2 ** powers[0] * 3 ** powers[1] * 5 ** powers[2] * 7 ** powers[3]


def wrap_flac(folder, sequence_id, family):
    """Repackage lossless subframes after checking instrument timestamp continuity."""
    folder = Path(folder)
    rows = 0
    total = 0
    last = None
    rate = None
    blocksize = None
    first_receipt = None
    startup_omitted = 0
    ticks = ticks_per_second(family)
    deadline = time.monotonic() + 60
    target = folder / "audio.partial.flac"
    with (folder / "original.webxi").open("rb") as source, target.open("xb") as output:
        output.write(b"\0" * 42)
        for line in (folder / "messages.jsonl").open(encoding="utf-8"):
            if time.monotonic() > deadline:
                raise TimeoutError("Audio repack time limit; originals retained")
            meta = json.loads(line)
            if meta.get("version") != 0 or not 24 <= meta["bytes"] <= 1048600:
                raise ValueError("Unsupported audio content version or size")
            if meta["type"] != 1:
                continue
            source.seek(meta["offset"])
            raw = source.read(meta["bytes"])
            if hashlib.sha256(raw).hexdigest() != meta["sha256"]:
                raise ValueError("Original audio hash mismatch")
            result = flac_block(raw, sequence_id)
            if result is None:
                continue
            frame, samples, number = result
            stamp = meta["device_time_raw"]
            if (
                last
                and stamp <= last[0]
                and rows == 1
                and last[0] > ticks * 1_000_000_000
                and 0 <= stamp < ticks * 3600
            ):
                # Observed startup transition: first message uses absolute time, subsequent
                # messages use relative time. Retain it in the raw archive, but don't guess
                # that its samples are continuous with the new epoch.
                output.seek(42)
                output.truncate()
                rows = total = 0
                last = None
                startup_omitted = 1
            if last:
                delta = stamp - last[0]
                if delta <= 0 or samples != blocksize:
                    raise ValueError("Audio timing/frame gap; original stream retained")
                quotient, remainder = divmod(samples * ticks, delta)
                if remainder or not 1 <= quotient < 1048576 or (rate and rate != quotient):
                    raise ValueError("Inconsistent audio sample timing; originals retained")
                rate = quotient
            if rows == 0:
                first_receipt = meta.get("pc_monotonic")
            blocksize = samples
            last = stamp, number
            total += samples
            output.write(renumber_frame(frame, rows))
            rows += 1
        if rows < 3 or rate is None:
            raise ValueError("Too few audio frames to establish sample timing")
        packed = (rate << 44) | (23 << 36) | total  # mono, 24-bit; verified above
        header = b"fLaC\x80\x00\x00\x22" + struct.pack(">HH", blocksize, blocksize)
        header += b"\0" * 6 + packed.to_bytes(8, "big") + b"\0" * 16
        output.seek(0)
        output.write(header)
    target.rename(folder / "audio.flac")
    return {
        "sample_rate_hz": rate,
        "channels": 1,
        "bits_per_sample": 24,
        "samples": total,
        "duration_s": total / rate,
        "frames": rows,
        "first_pc_monotonic": first_receipt,
        "startup_frames_omitted": startup_omitted,
        "startup_policy": "If the first timestamp switches from absolute to relative, the first frame is omitted from the playable copy only; original bytes remain in original.webxi.",
        "sample_rate_origin": "Calculated from FLAC sample counts, consecutive instrument timestamps and advertised Web-XI TimeFamily; checked for every frame",
        "format": "Lossless FLAC subframes; app-generated STREAMINFO and continuous frame numbering/checksums; originals retained; no gain, resampling or weighting",
    }


def capture_audio(
    connection, parent, preview, *, temporary_analysis, seconds, cancelled, progress, sync_id=None
):
    if not 1 <= seconds <= 3600:
        raise ValueError("Audio duration must be 1–3600 seconds")
    folder = Path(parent) / (
        "BnKG-Audio-" + datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ-") + uuid4().hex[:8]
    )
    folder.mkdir(parents=True)
    manifest = {
        "status": "preparing",
        "clock_id": CAPTURE_CLOCK_ID,
        "sync_id": sync_id,
        "quality": "Unknown: quality messages are not decoded; not a calibrated acoustic measurement",
        "privacy": "May contain conversations; private local capture",
        "measurement_control": "No Start/Pause/Stop",
        "started_utc": datetime.now(UTC).isoformat(),
        "temporary_analysis": temporary_analysis,
    }

    def save():
        tmp = folder / "audio.json.tmp"
        tmp.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
        tmp.replace(folder / "audio.json")

    save()
    client = AudioClient(**connection)
    restore_needed = False
    selected = None
    try:
        now = client.inspect_audio()
        if now != preview:
            raise PermissionError("Audio settings changed since inspection; inspect again")
        if cancelled():
            raise InterruptedError("Cancelled before setup")
        if temporary_analysis:
            # Mark before the request: even an ambiguous PUT must trigger read-only restoration inspection.
            restore_needed = True
            client.set_analysis_quality(1, expected=0, confirmations=2)
            now = client.inspect_audio()
        selected = next((s for s in now["sequences"] if s["format"] == "flac"), None)
        if selected is None:
            raise ValueError("No advertised FLAC audio sequence")
        family = selected["descriptor"].get("TimeFamily")
        if family is None:
            family = client._request_json("/WebXi/Device/TimeFamily")
        ticks_per_second(family)
        manifest.update(sequence=selected, time_family=family)
        save()
        if cancelled():
            raise InterruptedError("Cancelled before stream setup")
        client.open_audio(selected, confirmed=True)
        manifest["status"] = "capturing"
        save()
        start = time.monotonic()
        count = 0
        with (
            (folder / "original.webxi").open("xb") as rawfile,
            (folder / "messages.jsonl").open("x", encoding="utf-8") as ledger,
        ):
            while not cancelled() and time.monotonic() - start < seconds:
                try:
                    raw, meta = client.read_message(cancelled)
                except InterruptedError:
                    break
                if (
                    rawfile.tell() + len(raw) > 192 * 1024 * 1024
                    or count >= 60000
                    or shutil.disk_usage(folder).free < 64 * 1024 * 1024
                ):
                    raise OSError("Audio size, message or free-space limit reached")
                meta.update(
                    offset=rawfile.tell(),
                    bytes=len(raw),
                    sha256=hashlib.sha256(raw).hexdigest(),
                    pc_utc=datetime.now(UTC).isoformat(),
                    pc_monotonic=time.monotonic(),
                )
                rawfile.write(raw)
                ledger.write(json.dumps(meta) + "\n")
                count += 1
                if count % 16 == 0:
                    progress(
                        f"Audio: {count} messages · {time.monotonic() - start:.0f} s · {folder}"
                    )
        manifest.update(status="captured", messages=count, stopped_by_user=cancelled())
    except Exception as exc:
        manifest.update(status="incomplete", error=str(exc))
    finally:
        try:
            client.close_audio()
            manifest["stream_closed"] = True
        except Exception as exc:
            manifest["cleanup_error"] = str(exc)
        client.close()
        if restore_needed:
            restore = AudioClient(**connection)
            try:
                value = restore.get(SETUP, recursive=True).get("AudioRecordingAnalysisQuality")
                if value == 1:
                    restore.set_analysis_quality(0, expected=1, confirmations=2)
                elif value != 0:
                    raise PermissionError("Analysis quality changed externally; not overwritten")
                manifest["setting_restored"] = (
                    restore.get(SETUP, recursive=True).get("AudioRecordingAnalysisQuality") == 0
                )
                manifest["state_final"] = restore.get(STATE)
            except Exception as exc:
                manifest["restore_error"] = (
                    "CHECK INSTRUMENT: Analysis quality may remain Continuous. " + str(exc)
                )
            finally:
                restore.close()
        save()
    if manifest["status"] == "captured" and selected:
        try:
            manifest["audio"] = wrap_flac(folder, selected["id"], manifest["time_family"])
            manifest["status"] = "complete"
        except Exception as exc:
            manifest.update(status="raw_only", conversion_error=str(exc))
    if manifest.get("restore_error") or manifest.get("cleanup_error"):
        manifest["status"] = "needs_attention"
    save()
    return folder, manifest
