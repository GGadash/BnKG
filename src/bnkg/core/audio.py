"""Narrow instrument audio transport. No measurement, calibration or generic writes."""

import json
import re
import struct
import time
from urllib.parse import urlencode, urlsplit
from uuid import uuid4

from websockets.sync.client import connect

from bnkg.core.safety import require_allowed
from bnkg.core.webxi import SEQUENCES, SETUP, STATE, WebXiClient, WebXiError

ANALYSIS = SETUP + "/AudioRecordingAnalysisQuality"
STREAMS = "/WebXi/Streams"
MAX_MESSAGE = 1024 * 1024


def audio_sequences(tree):
    result = []

    def walk(node, key=""):
        if not isinstance(node, dict):
            return
        if "Name" in node:
            fmt = str(node.get("MessageFormat", node.get("DataFormat", ""))).lower()
            if fmt in {"flac", "mp3"} and node.get("Direction", "FromDevice") == "FromDevice":
                if not re.fullmatch(r"[1-9][0-9]{0,4}", key) or int(key) > 32767:
                    raise ValueError("Unsupported audio sequence identifier.")
                result.append({"id": int(key), "format": fmt, "descriptor": dict(node)})
            return
        for name, child in node.items():
            walk(child, name)

    walk(tree)
    return result


class AudioClient(WebXiClient):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.stream_path = None
        self.creation_pending = False
        self.stream_name = "BnKG-audio-" + uuid4().hex
        self.audio_socket = None

    def inspect_audio(self):
        return {
            "state": self.get(STATE),
            "setup": {
                key: value
                for key, value in self.get(SETUP, recursive=True).items()
                if key in {"AudioRecordingAnalysisQuality", "AudioRecordingLiveStreamMP3Flac"}
            },
            "sequences": audio_sequences(self.get(SEQUENCES, recursive=True)),
        }

    def set_analysis_quality(self, value, *, expected, confirmations=0):
        require_allowed("configure_audio_analysis")
        if (
            confirmations != 2
            or type(value) is not int
            or type(expected) is not int
            or value not in (0, 1)
            or expected not in (0, 1)
        ):
            raise PermissionError("Confirm the exact Analysis quality change twice.")
        if self.uncertain or self.get(STATE) != "Activated":
            raise PermissionError("Analysis quality changes require verified idle Activated state.")
        setup = self.get(SETUP, recursive=True)
        metadata = (
            self.get(SETUP, recursive=True, metadata=True)
            .get("AudioRecordingAnalysisQuality", {})
            .get("Metadata", {})
        )
        if setup.get("AudioRecordingAnalysisQuality") != expected:
            raise PermissionError(
                "Analysis quality changed since preview; inspect before changing it."
            )
        if "ReadOnly" in str(metadata.get("Flags", "")) or value not in metadata.get(
            "Domain", {}
        ).get("List", {}).get("Values", []):
            raise PermissionError("Analysis quality is not advertised writable with this value.")
        if value == expected:
            return
        try:
            with self.session.put(
                self.address + ANALYSIS,
                json=value,
                params={"password": self.password} if self.password else None,
                timeout=self.timeout,
                allow_redirects=False,
            ) as reply:
                if reply.status_code != 200:
                    raise WebXiError("Audio setting was not acknowledged.")
            if (
                self.get(SETUP, recursive=True).get("AudioRecordingAnalysisQuality") != value
                or self.get(STATE) != "Activated"
            ):
                raise WebXiError("Audio setting read-back/state mismatch.")
        except Exception:
            self.uncertain = True
            raise WebXiError(
                "Audio setting outcome uncertain; no retry. Inspect the instrument and refresh before another change."
            ) from None

    def open_audio(self, sequence, *, confirmed=False):
        require_allowed("receive_audio_stream")
        if not confirmed or self.stream_path or self.uncertain:
            raise PermissionError("Confirm one new receive-only audio stream.")
        current = audio_sequences(self.get(SEQUENCES, recursive=True))
        if sequence not in current:
            raise PermissionError("Audio sequence changed or is unavailable; refresh first.")
        body = {
            "ConnectionType": "WebSocket",
            "Name": self.stream_name,
            "Sequences": [sequence["id"]],
            "MessageTypes": ["SequenceData"],
        }
        self.creation_pending = True
        try:
            with self.session.post(
                self.address + STREAMS,
                json=body,
                params={"password": self.password} if self.password else None,
                timeout=self.timeout,
                allow_redirects=False,
                stream=True,
            ) as reply:
                if reply.status_code not in (200, 201):
                    self.creation_pending = False
                    raise WebXiError(f"Audio stream creation refused: HTTP {reply.status_code}.")
                data = bytearray()
                deadline = time.monotonic() + 8
                for part in reply.iter_content(4096):
                    data.extend(part)
                    if len(data) > 16384 or time.monotonic() > deadline:
                        raise WebXiError("Oversized stream response.")
                uris = json.loads(data).get("URI")
            if (
                not isinstance(uris, list)
                or len(uris) != 1
                or not isinstance(uris[0], str)
                or not re.fullmatch(r"/webxi/streams/[0-9]+", uris[0], re.I)
            ):
                raise WebXiError(
                    "Unrecognized owned-stream URI; inspect streams on the instrument."
                )
            self.stream_path = uris[0]
            self.creation_pending = False
            info = self._request_json(self.stream_path, recursive=True)
            if (
                info.get("Name") != self.stream_name
                or info.get("Direction", "FromDevice") != "FromDevice"
                or info.get("IsOutput", False) is not False
                or info.get("ConnectionType") != "WebSocket"
            ):
                raise WebXiError("Stream ownership/type verification failed.")
            address = urlsplit(self.address)
            uri = (
                ("wss" if address.scheme == "https" else "ws")
                + "://"
                + address.netloc
                + self.stream_path
            )
            if self.password:
                uri += "?" + urlencode({"password": self.password})
            self.audio_socket = connect(
                uri,
                proxy=None,
                compression=None,
                open_timeout=3,
                close_timeout=1,
                ping_interval=None,
                max_size=MAX_MESSAGE + 24,
                max_queue=4,
            )
            return info
        except Exception:
            self.uncertain = True
            raise

    def read_message(self, cancelled):
        deadline = time.monotonic() + 8

        while True:
            if cancelled():
                raise InterruptedError("Audio capture stopped.")
            if time.monotonic() > deadline:
                raise WebXiError("Audio stream stalled; no automatic restart.")
            try:
                raw = self.audio_socket.recv(timeout=0.5)
                break
            except TimeoutError:
                continue
        if not isinstance(raw, bytes) or len(raw) < 24:
            raise ValueError("Unsupported Web-XI binary audio message.")
        header, payload = raw[:24], raw[24:]
        magic, length, kind, version, reserved, timestamp, size = struct.unpack("<HHHHIQI", header)
        if magic != 0x4B42 or length != 16 or size > MAX_MESSAGE or len(payload) != size:
            raise ValueError("Unsupported or oversized Web-XI audio message.")
        return header + payload, {
            "type": kind,
            "version": version,
            "device_time_raw": timestamp,
            "payload_bytes": size,
        }

    def close_audio(self):
        if self.creation_pending and not self.stream_path:
            raise WebXiError(
                "Stream creation outcome uncertain. Inspect the instrument streams before retrying; no unowned stream was deleted."
            )
        if self.audio_socket:
            self.audio_socket.close()
            self.audio_socket = None
        if self.stream_path:
            # Closing the socket normally removes the resource. Never delete a
            # resource without verifying our unique name and receive-only direction.
            streams = self._request_json(STREAMS, recursive=True)
            entry = streams.get(self.stream_path.rsplit("/", 1)[-1])
            if entry is not None:
                if (
                    entry.get("Name") != self.stream_name
                    or entry.get("Direction", "FromDevice") != "FromDevice"
                    or entry.get("IsOutput", False) is not False
                ):
                    raise PermissionError("Refusing cleanup of an unowned stream.")
                with self.session.delete(
                    self.address + self.stream_path,
                    params={"password": self.password} if self.password else None,
                    timeout=self.timeout,
                    allow_redirects=False,
                ) as reply:
                    if reply.status_code not in (200, 204, 404):
                        raise WebXiError("Owned audio stream cleanup was not acknowledged.")
            self.stream_path = None
