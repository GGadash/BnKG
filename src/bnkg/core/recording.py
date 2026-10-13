"""Bounded original-frame archive and optional external encoder; no device access."""

import hashlib
import json
import math
import os
import shutil
import struct
import subprocess
import time
import uuid
from datetime import UTC, datetime
from pathlib import Path

from bnkg.core.capture_clock import CAPTURE_CLOCK_ID

MAX_BYTES = 512 * 1024 * 1024
MIN_FREE = 64 * 1024 * 1024
MAX_FRAMES = 3600
MAX_SECONDS = 3600


def png_size(data):
    if len(data) < 24 or len(data) > 8 * 1024 * 1024 or data[:8] != b"\x89PNG\r\n\x1a\n":
        raise ValueError("Invalid or oversized screen PNG.")
    size = struct.unpack(">II", data[16:24])
    if not all(0 < side <= 2048 for side in size):
        raise ValueError("Screen image dimensions exceed the recording limit.")
    return size


class RecordingCancelled(RuntimeError):
    pass


def run_tool(arguments, folder, cancelled, timeout=15, output_paths=()):
    """Bound both process lifetime and captured output; never invoke a shell."""
    if cancelled():
        raise RecordingCancelled("Encoding cancelled; original frames retained.")
    stdout, stderr = folder / "tool.stdout", folder / "tool.stderr"
    with stdout.open("wb") as out, stderr.open("wb") as err:
        process = subprocess.Popen(
            [str(a) for a in arguments],
            cwd=folder,
            stdin=subprocess.DEVNULL,
            stdout=out,
            stderr=err,
            shell=False,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        deadline = time.monotonic() + timeout
        try:
            while process.poll() is None:
                if cancelled():
                    raise RecordingCancelled("Encoding cancelled; original frames retained.")
                if time.monotonic() > deadline:
                    raise RuntimeError("Encoder/probe timed out; original frames retained.")
                if max(stdout.stat().st_size, stderr.stat().st_size) > 1024 * 1024:
                    raise RuntimeError("Encoder output exceeded its diagnostic limit.")
                for candidate in output_paths:
                    if candidate.exists() and candidate.stat().st_size > MAX_BYTES:
                        raise OSError("Media output exceeded 512 MiB; partial retained.")
                partial = folder / "video.partial.mp4"
                if partial.exists() and partial.stat().st_size > MAX_BYTES:
                    raise OSError("Encoded output exceeded the 512 MiB limit; partial retained.")
                if shutil.disk_usage(folder).free < MIN_FREE:
                    raise OSError("Low disk space; original frames retained.")
                time.sleep(0.05)
        finally:
            if process.poll() is None:
                process.kill()
                process.wait(timeout=5)
    if max(stdout.stat().st_size, stderr.stat().st_size) > 1024 * 1024:
        raise RuntimeError("Encoder output exceeded its diagnostic limit.")
    partial = folder / "video.partial.mp4"
    if partial.exists() and partial.stat().st_size > MAX_BYTES:
        raise OSError("Encoded output exceeded the 512 MiB limit; partial retained.")
    for candidate in output_paths:
        if candidate.exists() and candidate.stat().st_size > MAX_BYTES:
            raise OSError("Media output exceeded 512 MiB; partial retained.")
    if cancelled():
        raise RecordingCancelled("Encoding cancelled; original frames retained.")
    if process.returncode:
        raise RuntimeError("Encoder/probe failed: " + stderr.read_text(errors="replace")[-1500:])
    return stdout.read_text(encoding="utf-8", errors="replace")


class FrameArchive:
    def __init__(self, parent, *, profile="high", crf=18, sync_id=None):
        if profile not in {"baseline", "main", "high"} or not 1 <= crf <= 51:
            raise ValueError("Choose a supported AVC profile and CRF 1–51 (lossy video).")
        parent = Path(parent)
        parent.mkdir(parents=True, exist_ok=True)
        self.folder = parent / (
            "BnKG-SLM-" + datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ-") + uuid.uuid4().hex[:8]
        )
        self.folder.mkdir()  # Exclusive new recording; never reuse another archive.
        self.rows = []
        self.bytes = 0
        self.size = None
        self.profile, self.crf = profile, crf
        self.manifest = {
            "source": "instrument display PNG",
            "clock_id": CAPTURE_CLOCK_ID,
            "sync_id": sync_id,
            "status": "capturing",
            "audio": False,
            "timing": "PC UTC/monotonic receipt times, not instrument measurement times",
            "video_policy": "Processed lossy AVC; holds last frame across gaps. Consult frames.jsonl for stale/unchanged/gap evidence. PNG originals are unchanged. Input timing quantized to 40 ms; no motion interpolation.",
            "profile": profile,
            "crf": crf,
            "preset": "medium",
            "pixel_format": "yuv420p",
            "padding": "right/bottom to even dimensions; no scaling",
            "limits": {"png_bytes": MAX_BYTES, "frames": MAX_FRAMES, "seconds": MAX_SECONDS},
        }
        self.write_manifest()

    def write_manifest(self, **updates):
        self.manifest.update(updates)
        temporary = self.folder / "recording.json.tmp"
        temporary.write_text(json.dumps(self.manifest, indent=2), encoding="utf-8")
        temporary.replace(self.folder / "recording.json")

    def append(self, data, timing):
        size = png_size(data)
        if self.size and size != self.size:
            raise ValueError(
                "Screen resolution changed; recording stopped to preserve native frames."
            )
        stamp = float(timing["monotonic"])
        if not math.isfinite(stamp):
            raise ValueError("Invalid frame receipt time.")
        if self.rows and stamp <= self.rows[-1]["monotonic"]:
            raise ValueError("Non-increasing frame receipt time.")
        if len(self.rows) >= MAX_FRAMES or self.bytes + len(data) > MAX_BYTES:
            raise OSError("Recording frame/disk budget reached; originals retained.")
        if self.rows and stamp - self.rows[0]["monotonic"] > MAX_SECONDS:
            raise OSError("Recording duration limit reached; originals retained.")
        if shutil.disk_usage(self.folder).free < MIN_FREE + len(data):
            raise OSError("Low disk space; recording stopped.")
        name = f"frame-{len(self.rows):06d}.png"
        digest = hashlib.sha256(data).hexdigest()
        previous = self.rows[-1] if self.rows else None
        delta = stamp - previous["monotonic"] if previous else 0
        unchanged = bool(previous and previous["sha256"] == digest)
        row = {
            "file": name,
            "pc_utc": str(timing["pc_utc"]),
            "monotonic": stamp,
            "elapsed_s": stamp - self.rows[0]["monotonic"] if self.rows else 0,
            "sha256": digest,
            "bytes": len(data),
            "gap_before_s": delta if delta > 3 else 0,
            "unchanged": unchanged,
            "unchanged_for_s": previous["unchanged_for_s"] + delta if unchanged else 0,
        }
        with (self.folder / name).open("xb") as handle:
            handle.write(data)
        with (self.folder / "frames.jsonl").open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(row) + "\n")
            handle.flush()
        self.rows.append(row)
        self.bytes += len(data)
        self.size = size
        return row

    def finish_capture(self, reason, dropped=0):
        self.write_manifest(
            status="originals saved",
            reason=reason,
            dropped_frames=dropped,
            frames=len(self.rows),
            png_bytes=self.bytes,
            native_size=self.size,
        )

    def encode(self, ffmpeg, ffprobe, cancelled, runner=run_tool):
        if not self.rows:
            raise ValueError("No frames received; no video created.")
        self.write_manifest(status="encoding")
        version = runner([ffmpeg, "-version"], self.folder, cancelled).splitlines()[0]
        encoders = runner([ffmpeg, "-hide_banner", "-encoders"], self.folder, cancelled)
        if "libx264" not in encoders:
            raise ValueError("The selected FFmpeg build does not offer libx264.")
        durations = [
            b["monotonic"] - a["monotonic"] for a, b in zip(self.rows, self.rows[1:], strict=False)
        ]
        durations.append(1.0)  # Last received image displayed for an explicit one second.
        lines = ["ffconcat version 1.0"]
        for row, duration in zip(self.rows, durations, strict=True):
            lines.extend(["file " + row["file"], f"duration {duration:.6f}"])
        lines.append("file " + self.rows[-1]["file"])
        (self.folder / "frames.ffconcat").write_text("\n".join(lines) + "\n", encoding="ascii")
        partial = self.folder / "video.partial.mp4"
        runner(
            [
                ffmpeg,
                "-nostdin",
                "-hide_banner",
                "-loglevel",
                "error",
                "-n",
                "-f",
                "concat",
                "-safe",
                "1",
                "-i",
                "frames.ffconcat",
                "-vf",
                "pad=ceil(iw/2)*2:ceil(ih/2)*2",
                "-c:v",
                "libx264",
                "-profile:v",
                self.profile,
                "-crf",
                str(self.crf),
                "-preset",
                "medium",
                "-pix_fmt",
                "yuv420p",
                "-bf",
                "0",  # Sparse receipt-timed frames: avoid reordered-frame duration offsets.
                "-fps_mode",
                "vfr",
                "-movflags",
                "+faststart",
                partial.name,
            ],
            self.folder,
            cancelled,
            timeout=300,
        )
        probe = json.loads(
            runner(
                [
                    ffprobe,
                    "-v",
                    "error",
                    "-count_frames",
                    "-show_streams",
                    "-show_format",
                    "-of",
                    "json",
                    partial.name,
                ],
                self.folder,
                cancelled,
            )
        )
        video = [s for s in probe.get("streams", []) if s.get("codec_type") == "video"]
        expected = tuple(v + v % 2 for v in self.size)
        if (
            len(video) != 1
            or video[0].get("codec_name") != "h264"
            or (video[0].get("width"), video[0].get("height")) != expected
            or int(video[0].get("nb_read_frames", 0)) < len(self.rows)
            or abs(float(probe["format"]["duration"]) - sum(durations)) > 0.2
            or any(s.get("codec_type") == "audio" for s in probe["streams"])
        ):
            raise ValueError("Encoded video validation failed; originals and partial retained.")
        if cancelled():
            raise RecordingCancelled("Encoding cancelled; original frames retained.")
        os.link(partial, self.folder / "video.mp4")
        partial.unlink()
        self.write_manifest(
            status="complete",
            encoder_version=version,
            b_frames=0,
            probe=probe,
            video="video.mp4",
            duration_s=sum(durations),
            last_frame_hold_s=1,
        )
        return self.folder / "video.mp4"
