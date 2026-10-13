"""Bounded local audio export and receipt-aligned audio/video composition."""

import hashlib
import json
import math
import os
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from bnkg.core.recording import MAX_BYTES, RecordingCancelled, run_tool


def read_json(path, limit=2 * 1024 * 1024):
    path = Path(path)
    if path.stat().st_size > limit:
        raise ValueError("Metadata exceeds its size limit")
    return json.loads(path.read_text(encoding="utf-8"))


def digest(path, cancelled):
    result = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            if cancelled():
                raise RecordingCancelled("Media operation cancelled")
            result.update(chunk)
    return result.hexdigest()


def first_receipt(folder, filename, key):
    with (Path(folder) / filename).open(encoding="utf-8") as source:
        line = source.readline(16385)
    if len(line) > 16384:
        raise ValueError("Oversized timing record")
    value = float(json.loads(line)[key])
    if not math.isfinite(value):
        raise ValueError("Invalid receipt timestamp")
    return value


def sync_plan(audio_folder, video_folder, correction_ms=0):
    audio = read_json(Path(audio_folder) / "audio.json")
    video = read_json(Path(video_folder) / "recording.json")
    if audio.get("status") != "complete" or video.get("status") != "complete":
        raise ValueError("Both recordings must be finalized successfully")
    for key in ("clock_id", "sync_id"):
        if not audio.get(key) or audio[key] != video.get(key):
            raise ValueError("Recordings must come from the same paired capture session")
    correction = float(correction_ms) / 1000
    if not math.isfinite(correction) or abs(correction) > 30:
        raise ValueError("Manual correction must be within Â±30 seconds")
    audio_start = audio["audio"].get("first_pc_monotonic")
    if audio_start is None:
        audio_start = first_receipt(audio_folder, "messages.jsonl", "pc_monotonic")
    if not isinstance(audio_start, (int, float)) or not math.isfinite(audio_start):
        raise ValueError("Invalid first playable audio receipt")
    offset = audio_start - first_receipt(video_folder, "frames.jsonl", "monotonic") + correction
    duration = float(video["duration_s"])
    audio_duration = float(audio["audio"]["duration_s"])
    if not all(math.isfinite(v) and 0 < v <= 3602 for v in (duration, audio_duration)):
        raise ValueError("Invalid recording duration")
    overlap = min(duration, offset + audio_duration) - max(0, offset)
    if overlap <= 0:
        raise ValueError("The audio and video have no overlapping capture period")
    return {
        "offset_s": offset,
        "video_duration_s": duration,
        "audio_duration_s": audio_duration,
        "manual_correction_ms": correction_ms,
        "overlap_s": overlap,
        "alignment": "Estimated from PC monotonic receipt times in one paired capture; instrument/network/display latency is unknown. No drift correction or hardware-sync claim.",
        "outside_audio": "Silence outside the overlapping audio period; video holds frames across receipt gaps",
    }


def export_media(
    audio_path,
    parent,
    ffmpeg,
    ffprobe,
    *,
    codec="aac",
    video_folder=None,
    correction_ms=0,
    cancelled=lambda: False,
):
    audio_path = Path(audio_path).resolve()
    if audio_path.suffix.lower() not in {".flac", ".wav", ".m4a", ".opus", ".mp3"}:
        raise ValueError("Choose a local supported audio file")
    if not audio_path.is_file() or not 0 < audio_path.stat().st_size <= MAX_BYTES:
        raise ValueError("Audio source is missing or exceeds 512 MiB")
    if codec not in {"aac", "opus"}:
        raise ValueError("Unsupported output codec")
    for tool in (ffmpeg, ffprobe):
        if not tool or not Path(tool).is_file():
            raise ValueError("Choose FFmpeg and ffprobe in the recording tools controls")
    folder = Path(parent).resolve() / (
        "BnKG-Media-" + datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ-") + uuid4().hex[:8]
    )
    folder.mkdir(parents=True)
    manifest = {
        "status": "processing",
        "codec": "native AAC" if codec == "aac" else "libopus",
        "source_name": audio_path.name,
        "processing": "Lossy encode; resampled to 48000 Hz; no gain normalization or acoustic weighting",
        "originals_preserved": True,
    }

    def save():
        tmp = folder / "media.json.tmp"
        tmp.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
        tmp.replace(folder / "media.json")

    def run(args, outputs=(), timeout=30):
        return run_tool(args, folder, cancelled, timeout=timeout, output_paths=outputs)

    def probe(path):
        return json.loads(
            run(
                [
                    ffprobe,
                    "-v",
                    "error",
                    "-protocol_whitelist",
                    "file,pipe",
                    "-show_streams",
                    "-show_format",
                    "-of",
                    "json",
                    str(path),
                ]
            )
        )

    save()
    try:
        source_hash = digest(audio_path, cancelled)
        info = probe(audio_path)
        streams = [s for s in info.get("streams", []) if s.get("codec_type") == "audio"]
        duration = float(info.get("format", {}).get("duration", 0))
        if len(streams) != 1 or not math.isfinite(duration) or not 0 < duration <= 3602:
            raise ValueError("Require one audio stream of at most one hour")
        manifest.update(source_sha256=source_hash, source_probe=info)
        source_manifest = audio_path.parent / "audio.json"
        if audio_path.name == "audio.flac" and source_manifest.is_file():
            manifest["source_capture"] = read_json(source_manifest)
        args = [
            ffmpeg,
            "-nostdin",
            "-hide_banner",
            "-v",
            "error",
            "-xerror",
            "-n",
            "-protocol_whitelist",
            "file,pipe",
            "-i",
            str(audio_path),
        ]
        filters = "aresample=48000"
        if video_folder:
            if codec != "aac" or audio_path.name != "audio.flac":
                raise ValueError("Paired MP4 requires the captured audio.flac and native AAC")
            plan = sync_plan(audio_path.parent, video_folder, correction_ms)
            video_path = (Path(video_folder) / "video.mp4").resolve()
            if not video_path.is_file() or not 0 < video_path.stat().st_size <= MAX_BYTES:
                raise ValueError("Finalized screen video is missing or oversized")
            video_info = probe(video_path)
            if [s.get("codec_name") for s in video_info.get("streams", [])] != ["h264"]:
                raise ValueError("Expected one H.264 screen-video stream")
            if (
                abs(float(video_info["format"]["duration"]) - plan["video_duration_s"]) > 0.2
                or abs(duration - plan["audio_duration_s"]) > 0.05
            ):
                raise ValueError("Media duration disagrees with capture manifests")
            video_hash = digest(video_path, cancelled)
            manifest.update(synchronization=plan, video_sha256=video_hash)
            args += [
                "-protocol_whitelist",
                "file,pipe",
                "-i",
                str(video_path),
                "-map",
                "1:v:0",
                "-map",
                "0:a:0",
                "-c:v",
                "copy",
            ]
            offset = plan["offset_s"]
            if offset < 0:
                filters += f",atrim=start={-offset:.9f},asetpts=PTS-STARTPTS"
            else:
                filters += ",asetpts=PTS-STARTPTS"
                filters += f",adelay={round(offset * 48000)}S:all=1"
            duration = plan["video_duration_s"]
            filters += f",apad,atrim=duration={duration:.9f}"
            suffix = ".mp4"
        else:
            args += ["-map", "0:a:0", "-vn"]
            suffix = ".m4a" if codec == "aac" else ".opus"
        partial = folder / ("media.partial" + suffix)
        final = folder / ("media" + suffix)
        args += [
            "-af",
            filters,
            "-c:a",
            "aac" if codec == "aac" else "libopus",
            "-b:a",
            "128k",
            "-t",
            str(duration),
            "-map_metadata",
            "-1",
        ]
        if codec == "aac":
            args += ["-movflags", "+faststart"]
        args += [str(partial)]
        run(args, (partial,), timeout=300)
        result = probe(partial)
        output_audio = [s for s in result.get("streams", []) if s.get("codec_type") == "audio"]
        if (
            len(output_audio) != 1
            or output_audio[0].get("codec_name") != codec
            or int(output_audio[0].get("sample_rate", 0)) != 48000
            or abs(float(result["format"]["duration"]) - duration) > 0.2
        ):
            raise ValueError("Export probe did not match the requested codec/rate/duration")
        output_video = [s for s in result.get("streams", []) if s.get("codec_type") == "video"]
        if video_folder and [s.get("codec_name") for s in output_video] != ["h264"]:
            raise ValueError("Export is missing the expected H.264 video stream")
        if not video_folder and output_video:
            raise ValueError("Audio export unexpectedly contains video")
        if digest(audio_path, cancelled) != source_hash or (
            video_folder and digest(video_path, cancelled) != video_hash
        ):
            raise ValueError("Source changed during export; result not published")
        if cancelled():
            raise RecordingCancelled("Media export cancelled")
        output_hash = digest(partial, cancelled)
        if cancelled():
            raise RecordingCancelled("Media export cancelled")
        os.link(partial, final)
        partial.unlink()
        manifest.update(
            status="complete", output=final.name, output_sha256=output_hash, probe=result
        )
    except Exception as exc:
        manifest.update(
            status="cancelled" if isinstance(exc, RecordingCancelled) else "incomplete",
            error=str(exc),
        )
        save()
        raise
    save()
    return final
