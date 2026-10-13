"""Worker-owned acquisition, explicit local capture/logging and SLM actions."""

import hashlib
import json
import os
import traceback
from datetime import UTC, datetime
from pathlib import Path
from time import monotonic

from PySide6.QtCore import QObject, QThread, QTimer, Signal, Slot

from bnkg.core.device import DemoDevice
from bnkg.core.sessions import SessionStore
from bnkg.core.webxi import WebXiClient


class AcquisitionWorker(QObject):
    sample = Signal(object)
    captured = Signal(object)
    capture_changed = Signal(bool)
    status = Signal(str, str)
    session_changed = Signal(str, bool, int)
    failure = Signal(str)
    screen = Signal(bytes)
    recording_frame = Signal(bytes, object)
    screen_status = Signal(str)
    controls = Signal(bool, object)
    keypad_state = Signal(bool)
    connected = Signal(str, object)
    location_previewed = Signal(object)
    location_written = Signal(object)
    finished = Signal()

    def __init__(self, audit_dir=None) -> None:
        super().__init__()
        self.audit_dir = Path(audit_dir) if audit_dir else None
        self.device = None
        self.store = None
        self.timer = None
        self.session_path = ""
        self.mode = "disconnected"
        self.stopped = False
        self.read_errors = 0
        self.capturing = False
        self.screen_enabled = False
        self.recording_screen = False
        self.screen_digest = ""
        self.screen_received = 0.0

    @Slot()
    def start(self):
        self.timer = QTimer(self)
        self.timer.setInterval(1000)
        self.timer.timeout.connect(self.poll)

    @Slot(str, object)
    def command(self, name: str, value: object = None):
        if self.stopped:
            return
        try:
            if name in {"demo", "connect", "disconnect"}:
                self.disconnect()
                if name == "disconnect":
                    return
                if name == "demo":
                    self.device = DemoDevice(str(value or "Smooth"))
                    self.mode = "simulation"
                    self.status.emit("simulation", f"{self.device.demo_mode} demo • synthetic")
                else:
                    options = value if isinstance(value, dict) else {"address": str(value)}
                    client = WebXiClient(options["address"], password=options.get("password", ""))
                    self.status.emit("connecting", "Checking SLM identity and supported actions")
                    try:
                        identity = client.identify()
                    except Exception:
                        client.close()
                        self.status.emit("disconnected", "Connection failed")
                        raise
                    self.device = client
                    self.mode = "instrument"
                    self.connected.emit(client.address, identity)
                    self.controls.emit(
                        False,
                        sorted(
                            client.actions
                            & {
                                "StartPause",
                                "Stop",
                                "Identify",
                                "KeyUp",
                                "KeyDown",
                                "KeyLeft",
                                "KeyRight",
                                "KeyMenu",
                            }
                        ),
                    )
                    self.status.emit(
                        "instrument",
                        f"{identity.get('HostName', 'SLM')} • monitoring; controls disarmed",
                    )
                self.read_errors = 0
                self.poll()
                if self.device and self.timer:
                    self.timer.start()
            elif name == "toggle":
                if not isinstance(self.device, DemoDevice):
                    raise PermissionError("This button controls the demo only.")
                self.device.toggle()
                if self.store:
                    self.store.event("demo-control", "Running" if self.device.running else "Paused")
                self.status.emit(
                    "simulation",
                    f"{self.device.demo_mode} demo • {'running' if self.device.running else 'paused; no samples logged'}",
                )
                if self.device.running:
                    self.poll()
            elif name == "capture_start":
                if not self.device:
                    raise RuntimeError("Connect an SLM or start demo first.")
                self.capturing = True
                self.capture_changed.emit(True)
            elif name == "capture_stop":
                self.stop_logging()
                self.capturing = False
                self.capture_changed.emit(False)
            elif name == "log_start":
                if not self.device or self.store:
                    raise RuntimeError("Connect a source and stop existing logging first.")
                options = value if isinstance(value, dict) else {"path": str(value)}
                self.store = SessionStore(
                    Path(options["path"]), self.mode, report_context=options.get("report_context")
                )
                self.session_path = str(options["path"])
                self.store.event("logging-start", "Local file logging started")
                self.capturing = True
                self.capture_changed.emit(True)
                self.session_changed.emit(self.session_path, True, 0)
            elif name == "log_stop":
                self.stop_logging()
            elif name == "screen":
                self.screen_enabled = bool(value)
                if not self.screen_enabled and not self.recording_screen:
                    self.screen_status.emit(
                        "Display polling paused — return to SLM screen to update"
                    )
            elif name == "record_screen":
                self.recording_screen = bool(value) and isinstance(self.device, WebXiClient)
                if not self.recording_screen and not self.screen_enabled:
                    self.screen_status.emit(
                        "Display polling paused — return to SLM screen to update"
                    )
            elif name == "screen_context":
                if not isinstance(self.device, WebXiClient):
                    raise PermissionError("No SLM connected.")
                self.device.navigation_ready = False
                try:
                    if value.get("confirmed"):
                        if (
                            not self.device.armed
                            or self.device.uncertain
                            or monotonic() - self.screen_received > 5
                            or value.get("digest") != self.screen_digest
                            or not 0 <= monotonic() - value.get("confirmed_at", 0) <= 5
                        ):
                            raise PermissionError(
                                "Inspect a fresh measurement screen before enabling keys."
                            )
                        self.device.navigation_ready = True
                finally:
                    self.keypad_state.emit(self.device.navigation_ready)
            elif name in {"screen_arrow", "screen_menu"}:
                if not isinstance(self.device, WebXiClient):
                    raise PermissionError("No SLM connected.")
                try:
                    if (
                        not self.device.navigation_ready
                        or monotonic() - self.screen_received > 5
                        or not 0 <= monotonic() - value.get("confirmed_at", 0) <= 5
                    ):
                        self.device.navigation_ready = False
                        raise PermissionError(
                            "Inspect a fresh measurement screen and enable its keys."
                        )
                    if name == "screen_menu":
                        self.device.open_screen_menu(screen_confirmed=True)
                    else:
                        self.device.navigate_measurement_screen(
                            value["direction"], screen_confirmed=True
                        )
                finally:
                    self.keypad_state.emit(self.device.navigation_ready)
                    self.controls.emit(
                        self.device.armed,
                        sorted(
                            self.device.actions
                            & {
                                "StartPause",
                                "Stop",
                                "Identify",
                                "KeyUp",
                                "KeyDown",
                                "KeyLeft",
                                "KeyRight",
                                "KeyMenu",
                            }
                        ),
                    )
            elif name == "arm":
                if not isinstance(self.device, WebXiClient):
                    raise PermissionError("Connect a real SLM before arming its controls.")
                if value and self.device.uncertain:
                    raise PermissionError(
                        "Refresh control state after an uncertain action before re-arming."
                    )
                self.device.armed = bool(value)
                if not value:
                    self.device.navigation_ready = False
                    self.keypad_state.emit(False)
                self.controls.emit(
                    self.device.armed,
                    sorted(
                        self.device.actions
                        & {
                            "StartPause",
                            "Stop",
                            "Identify",
                            "KeyUp",
                            "KeyDown",
                            "KeyLeft",
                            "KeyRight",
                            "KeyMenu",
                        }
                    ),
                )
            elif name == "location_preview":
                if not isinstance(self.device, WebXiClient):
                    raise PermissionError("Connect an SLM first.")
                self.location_previewed.emit(self.device.preview_location(**value))
            elif name == "location_write":
                if not isinstance(self.device, WebXiClient):
                    raise PermissionError("Connect an SLM first.")
                try:
                    result = self.device.write_location(
                        value["token"],
                        confirmations=value["confirmations"],
                        audit=self.audit_location,
                    )
                    self.location_written.emit(result)
                finally:
                    self.controls.emit(
                        self.device.armed,
                        sorted(
                            self.device.actions
                            & {
                                "StartPause",
                                "Stop",
                                "Identify",
                                "KeyUp",
                                "KeyDown",
                                "KeyLeft",
                                "KeyRight",
                                "KeyMenu",
                            }
                        ),
                    )
            elif name == "identify_display":
                if not isinstance(self.device, WebXiClient):
                    raise PermissionError("No SLM connected.")
                self.device.identify_display(
                    confirmed=isinstance(value, dict) and value.get("confirmed") is True
                )
                self.controls.emit(
                    self.device.armed,
                    sorted(
                        self.device.actions
                        & {
                            "StartPause",
                            "Stop",
                            "Identify",
                            "KeyUp",
                            "KeyDown",
                            "KeyLeft",
                            "KeyRight",
                            "KeyMenu",
                        }
                    ),
                )
                self.status.emit(
                    "instrument", "Identify acknowledged; inspect display / light ring"
                )
            elif name == "slm_action":
                if not isinstance(self.device, WebXiClient):
                    raise PermissionError("No SLM connected.")
                action, confirmations = value
                try:
                    state = self.device.measurement_action(action, confirmations=confirmations)
                    self.status.emit("instrument", f"SLM state verified: {state}")
                    if self.store:
                        self.store.event("slm-control", f"{action}: verified {state}")
                finally:
                    self.controls.emit(
                        self.device.armed,
                        sorted(
                            self.device.actions
                            & {
                                "StartPause",
                                "Stop",
                                "Identify",
                                "KeyUp",
                                "KeyDown",
                                "KeyLeft",
                                "KeyRight",
                                "KeyMenu",
                            }
                        ),
                    )
            elif name == "refresh_control":
                if not isinstance(self.device, WebXiClient):
                    raise PermissionError("No SLM connected.")
                state = self.device.refresh_control_state()
                self.status.emit("instrument", f"Current SLM state: {state}; re-arm if needed")
            else:
                raise ValueError("Unknown local operation.")
        except Exception as exc:
            if isinstance(self.device, WebXiClient):
                self.controls.emit(
                    self.device.armed,
                    sorted(
                        self.device.actions
                        & {
                            "StartPause",
                            "Stop",
                            "Identify",
                            "KeyUp",
                            "KeyDown",
                            "KeyLeft",
                            "KeyRight",
                            "KeyMenu",
                        }
                    ),
                )
            self.failure.emit(str(exc))

    @Slot()
    def poll(self):
        if not self.device or QThread.currentThread().isInterruptionRequested():
            return
        # Pausing a demo freezes display without creating fresh timestamps or repeated log rows.
        if isinstance(self.device, DemoDevice) and not self.device.running:
            return
        try:
            sample = self.device.read()
            if self.read_errors:
                self.status.emit(self.mode, "Connection recovered; fresh data")
            self.read_errors = 0
            if self.store:
                try:
                    self.store.append(sample)
                    self.session_changed.emit(self.session_path, True, self.store.count)
                except Exception as exc:
                    self.stop_logging()
                    self.failure.emit(f"Logging stopped: {exc}")
            self.sample.emit(sample)
            if self.capturing:
                self.captured.emit(sample)
        except Exception as exc:
            self.read_errors += 1
            if isinstance(self.device, WebXiClient):
                self.device.armed = False
                self.device.navigation_ready = False
                self.keypad_state.emit(False)
                self.controls.emit(
                    False,
                    sorted(
                        self.device.actions
                        & {
                            "StartPause",
                            "Stop",
                            "Identify",
                            "KeyUp",
                            "KeyDown",
                            "KeyLeft",
                            "KeyRight",
                            "KeyMenu",
                        }
                    ),
                )
            self.screen_status.emit("Screen stale; connection read failed")
            self.status.emit("stale", f"No fresh data • {exc}")
            if self.read_errors >= 3:
                self.disconnect()
                self.failure.emit(
                    "Connection stopped after three failed reads. Reconnect explicitly."
                )
            return
        if (self.screen_enabled or self.recording_screen) and isinstance(self.device, WebXiClient):
            try:
                png = self.device.screen_image()
                self.screen_received = monotonic()
                self.screen_digest = hashlib.sha256(png).hexdigest()
                if self.recording_screen:
                    self.recording_frame.emit(
                        png,
                        {
                            "monotonic": self.screen_received,
                            "pc_utc": datetime.now(UTC).isoformat(),
                        },
                    )
                self.screen.emit(png)
                self.screen_status.emit("Live SLM display • view only • 1 second polling")
            except Exception as exc:
                self.device.navigation_ready = False
                self.keypad_state.emit(False)
                self.screen_received = 0.0
                self.screen_status.emit(str(exc))

    def audit_location(self, outcome, preview):
        if self.audit_dir is None:
            raise OSError("Location audit directory is not configured; write blocked.")
        self.audit_dir.mkdir(parents=True, exist_ok=True)
        record = {
            "pc_utc": datetime.now(UTC).isoformat(),
            "operation": "location-text-metadata",
            "outcome": outcome,
            **{k: v for k, v in preview.items() if k != "created"},
        }
        with (self.audit_dir / "BnKG-Location-Writes.jsonl").open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")
            handle.flush()
            os.fsync(handle.fileno())

    def stop_logging(self):
        if self.store:
            store, self.store = self.store, None
            try:
                store.close()
            finally:
                self.session_changed.emit(self.session_path, False, store.count)

    def disconnect(self):
        self.recording_screen = False
        self.screen_digest = ""
        self.screen_received = 0.0
        if self.timer:
            self.timer.stop()
        self.stop_logging()
        self.capturing = False
        self.capture_changed.emit(False)
        if self.device:
            self.device.close()
            self.device = None
        self.mode = "disconnected"
        self.controls.emit(False, [])
        self.screen_status.emit("No SLM screen connected")
        self.status.emit("disconnected", "No instrument connected")

    @Slot()
    def shutdown(self):
        self.stopped = True
        try:
            self.disconnect()
        except Exception:
            traceback.print_exc()
        finally:
            self.finished.emit()
