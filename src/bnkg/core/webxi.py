"""Independently implemented, bounded read-only Web-XI client.

Endpoint evidence is recorded in docs/WEBXI_REFERENCES.md. Only explicitly armed measurement/Identify actions and reviewed location-text
metadata writes are permitted; no generic settings or stream setup.
"""

import ipaddress
import json
import re
import time
from datetime import UTC, datetime
from urllib.parse import urlsplit
from uuid import uuid4

import requests

from bnkg.core.location import coordinate_text
from bnkg.core.measurements import (
    decode_outputs,
    device_health_fields,
    metadata_snapshot,
    sequence_index,
)
from bnkg.core.parameters import Sample
from bnkg.core.safety import require_allowed

ROOT = "/webxi"
DEVICE = ROOT + "/device"
STATE = ROOT + "/Applications/SLM/State"
OUTPUTS = ROOT + "/Applications/SLM/Outputs"
LAF = OUTPUTS + "/LAF"
SETUP = ROOT + "/Applications/SLM/Setup"
APPLICATION = ROOT + "/Applications/SLM"
DISPLAY_ENABLED = SETUP + "/NetworkWebserverDisplay"
SCREEN_PATH = "/display/tmp/screenDump.png"
BATTERY = DEVICE + "/Battery"
DISKS = DEVICE + "/Disks"
SEQUENCES = ROOT + "/Sequences"
READ_PATHS = {
    BATTERY,
    DISKS,
    ROOT,
    DEVICE,
    STATE,
    OUTPUTS,
    LAF,
    SETUP,
    APPLICATION,
    DISPLAY_ENABLED,
    SEQUENCES,
}


class WebXiError(RuntimeError):
    pass


def normalize_address(address: str) -> str:
    value = address.strip()
    if not value or any(c.isspace() for c in value) or any(c in value for c in "\\?#@%"):
        raise ValueError("Enter an IP address or hostname, optionally with http(s) and a port.")
    if "://" not in value:
        try:
            ip = ipaddress.ip_address(value)
            value = f"[{ip}]" if ip.version == 6 else str(ip)
        except ValueError:
            pass
        value = "http://" + value
    try:
        parsed = urlsplit(value)
        host, port = parsed.hostname, parsed.port
    except ValueError as exc:
        raise ValueError("Invalid device address or port.") from exc
    if parsed.scheme not in {"http", "https"} or parsed.path not in {"", "/"} or not host:
        raise ValueError("Use an HTTP(S) device address without a path.")
    if port is not None and not 1 <= port <= 65535:
        raise ValueError("Device port must be between 1 and 65535.")
    try:
        ip = ipaddress.ip_address(host)
        host = f"[{ip}]" if ip.version == 6 else str(ip)
    except ValueError:
        if re.fullmatch(r"[0-9.]+", host):
            raise ValueError("Invalid IPv4 address.") from None
        host = host.encode("idna").decode("ascii")
        if len(host) > 253 or any(
            not re.fullmatch(r"[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?", label)
            for label in host.split(".")
        ):
            raise ValueError("Invalid hostname.") from None
    return f"{parsed.scheme}://{host}" + (f":{port}" if port is not None else "")


class WebXiClient:
    def __init__(
        self,
        address: str,
        session: requests.Session | None = None,
        *,
        password: str = "",
        timeout: tuple[float, float] = (2.0, 3.0),
    ) -> None:
        self.address = normalize_address(address)
        self.session = session or requests.Session()
        self.session.trust_env = False  # No ambient proxy or .netrc credentials for the SLM.
        self.started = time.monotonic()
        self.password = password
        self.timeout = timeout
        self.actions: set[str] = set()
        self.armed = False
        self.navigation_ready = False
        self.uncertain = False
        self.identity: dict = {}
        self.sequences = {}
        self.setup = {}
        self.setup_metadata = {}
        self.capabilities_at = 0.0
        self.health_groups = set()
        self.health = {}
        self.health_definitions = {}
        self.health_at = 0.0
        self.location_preview = None

    def get(self, path: str, *, recursive: bool = False, metadata: bool = False) -> object:
        if path not in READ_PATHS:
            raise ValueError("Endpoint has not been verified for this read-only probe.")
        if recursive and path not in {DEVICE, OUTPUTS, SETUP, SEQUENCES, BATTERY, DISKS}:
            raise ValueError("Recursive acquisition is limited to verified read roots.")
        return self._request_json(path, recursive=recursive, metadata=metadata)

    def _request_json(self, path: str, *, recursive=False, metadata=False):
        """Bounded transport; callers must validate the endpoint before calling."""
        flags = [
            flag for flag, enabled in (("recursive", recursive), ("metadata", metadata)) if enabled
        ]
        url = self.address + path + ("?" + "&".join(flags) if flags else "")
        try:
            with self.session.get(
                url,
                timeout=self.timeout,
                allow_redirects=False,
                stream=True,
                params={"password": self.password} if self.password else None,
            ) as reply:
                if 300 <= reply.status_code < 400:
                    raise WebXiError("Device redirect refused; enter the device address directly.")
                reply.raise_for_status()
                buffer = bytearray()
                deadline = time.monotonic() + 6
                for chunk in reply.iter_content(chunk_size=16384):
                    buffer.extend(chunk)
                    if len(buffer) > 2_000_000 or time.monotonic() > deadline:
                        raise WebXiError("Device response exceeded the probe size/time limit.")
                return json.loads(buffer.decode("utf-8-sig"))
        except requests.exceptions.SSLError:
            raise WebXiError(
                "TLS verification failed. Check the instrument certificate/address; certificate validation was not bypassed."
            ) from None
        except requests.Timeout:
            raise WebXiError(
                "Web-XI request timed out. Check that the SLM is awake, reachable and on the selected network."
            ) from None
        except requests.HTTPError as exc:
            status = exc.response.status_code if exc.response is not None else None
            if status in {401, 403}:
                message = "Web-XI access denied. Check the password and permitted instrument access; this response alone does not identify a missing licence."
            elif status == 404:
                message = "Web-XI endpoint unavailable (HTTP 404). Check the address and this model/firmware's supported API."
            else:
                message = "Web-XI returned an HTTP error. Check instrument status and supported API access."
            raise WebXiError(message) from None
        except requests.ConnectionError:
            raise WebXiError(
                "Cannot reach the Web-XI address. Check the IP/hostname, port, network and instrument availability."
            ) from None
        except requests.RequestException:
            raise WebXiError(
                "Web-XI request failed. Check the address, password and supported access."
            ) from None
        except (UnicodeError, ValueError) as exc:
            raise WebXiError("Web-XI response is not valid UTF-8 JSON.") from exc

    def identify(self) -> dict:
        root = self.get(ROOT)
        if not isinstance(root, dict) or not any(k.lower() == "device" for k in root):
            raise WebXiError("This address does not identify a Web-XI device.")
        identity = self.get(DEVICE, recursive=True)
        if not isinstance(identity, dict) or identity.get("Family") != "SLM":
            raise WebXiError("This Web-XI device is not identified as a sound level meter.")
        self.health_groups = {k for k in ("Battery", "Disks") if isinstance(identity.get(k), dict)}
        # Never retain Access/Challenge, licence keys or other unrelated identity data.
        self.identity = {k: identity.get(k, "") for k in ("Id", "HostName", "Type", "Version")}
        metadata = self.get(APPLICATION, metadata=True)
        items = (
            metadata.get("Metadata", {}).get("Actions", []) if isinstance(metadata, dict) else []
        )
        self.actions = {
            v["Name"] for v in items if isinstance(v, dict) and isinstance(v.get("Name"), str)
        }
        return self.identity

    def screen_image(self) -> bytes:
        if self.get(DISPLAY_ENABLED) != 1:
            raise WebXiError(
                "Enable Web server display on the SLM under System settings > Network settings."
            )
        try:
            with self.session.get(
                self.address + SCREEN_PATH,
                params={"password": self.password} if self.password else None,
                timeout=self.timeout,
                allow_redirects=False,
                stream=True,
            ) as reply:
                if reply.status_code != 200:
                    raise WebXiError(
                        "Screen image unavailable on this firmware. Check Web server display on the SLM."
                    )
                data = bytearray()
                deadline = time.monotonic() + 6
                for block in reply.iter_content(16384):
                    data.extend(block)
                    if len(data) > 3_000_000 or time.monotonic() > deadline:
                        raise WebXiError("Screen image exceeds size/time limit.")
                if not data.startswith(b"\x89PNG\r\n\x1a\n"):
                    raise WebXiError("Screen response is not a PNG image.")
                return bytes(data)
        except requests.RequestException:
            raise WebXiError(
                "Screen request failed; check connection and display access."
            ) from None

    def _location_slot(self, slot):
        if type(slot) is not int or not 1 <= slot <= 9:
            raise ValueError("Choose metadata slot 1 through 9.")
        if self.uncertain:
            raise PermissionError("Resolve the previous uncertain action before preparing a write.")
        if self.get(STATE) != "Activated":
            raise PermissionError(
                "Location metadata writes require an idle SLM with no pending result (Activated)."
            )
        setup = self.get(SETUP, recursive=True)
        definitions = self.get(SETUP, recursive=True, metadata=True)
        key = f"Metadata{slot}Text"
        if not isinstance(setup, dict) or not isinstance(definitions, dict):
            raise WebXiError("Unexpected metadata schema.")
        meta = definitions.get(key, {}).get("Metadata", {})
        if (
            setup.get("MetadataAll") != 1
            or setup.get(f"Metadata{slot}Metadata") != 1
            or setup.get(f"Metadata{slot}Type") != 0
        ):
            raise PermissionError(
                "On the physical SLM enable Metadata and the selected slot, set its type to Text, then preview again. B&KG does not change these settings automatically."
            )
        if meta.get("DataType") != "String" or "Flags" not in meta or "ReadOnly" in meta["Flags"]:
            raise PermissionError(
                "This slot is read-only or its write access is unknown; no write will be sent."
            )
        if not isinstance(setup.get(key), str) or not isinstance(
            setup.get(f"Metadata{slot}Name"), str
        ):
            raise WebXiError("Unexpected metadata value/name format.")
        return {"name": setup[f"Metadata{slot}Name"], "before": setup[key]}

    def preview_location(self, slot, latitude, longitude, source="manual"):
        self.location_preview = None
        text = coordinate_text(latitude, longitude)
        if source not in {"manual", "user-default", "slm-reported"}:
            raise ValueError("Unsupported location source.")
        fields = self._location_slot(slot)
        preview = {
            "token": str(uuid4()),
            "slot": slot,
            **fields,
            "after": text,
            "address": self.address,
            "source": source,
            "created": time.monotonic(),
        }
        self.location_preview = dict(preview)
        return dict(preview)

    def write_location(self, token, *, confirmations, audit):
        require_allowed("write_location_metadata")
        preview, self.location_preview = self.location_preview, None
        if not self.armed or self.uncertain or confirmations != 2:
            raise PermissionError("Arm SLM controls and confirm the location preview twice.")
        if not preview or token != preview["token"] or time.monotonic() - preview["created"] > 60:
            raise PermissionError("Location preview expired or changed; prepare a fresh preview.")
        current = self._location_slot(preview["slot"])
        if current != {"name": preview["name"], "before": preview["before"]}:
            raise PermissionError(
                "Slot changed since preview; no write sent. Review a fresh preview."
            )
        if not callable(audit):
            raise ValueError("A durable audit writer is required.")
        audit("attempt", preview)  # Fail before the PUT if the local audit cannot be saved.
        try:
            with self.session.put(
                self.address + SETUP + f"/Metadata{preview['slot']}Text",
                params={"password": self.password} if self.password else None,
                json=preview["after"],
                timeout=self.timeout,
                allow_redirects=False,
            ) as reply:
                if reply.status_code != 200:
                    raise WebXiError("Metadata write was not acknowledged.")
            verified = self._location_slot(preview["slot"])
            if verified != {"name": preview["name"], "before": preview["after"]}:
                raise WebXiError("Metadata read-back differs from the preview.")
            audit("verified", preview)
            self.capabilities_at = 0.0
            return dict(preview)
        except Exception:
            self.armed = False
            self.uncertain = True
            try:
                audit("uncertain", preview)
            except OSError:
                pass
            raise WebXiError(
                "Location write outcome uncertain; no retry sent. Inspect the slot on the SLM, refresh control state and prepare a new preview."
            ) from None

    def identify_display(self, *, confirmed=False):
        require_allowed("identify")
        if not confirmed or not self.armed or "Identify" not in self.actions or self.uncertain:
            raise PermissionError(
                "Arm supported SLM controls before Identify; resolve uncertain actions first."
            )
        try:
            with self.session.put(
                self.address + APPLICATION,
                params={
                    "Action": "Identify",
                    **({"password": self.password} if self.password else {}),
                },
                data=b"",
                timeout=self.timeout,
                allow_redirects=False,
            ) as reply:
                if reply.status_code != 200:
                    raise WebXiError("Identify was not acknowledged.")
            # State read-back establishes continued reachability, not proof of illumination.
            self.get(STATE)
        except Exception:
            self.armed = False
            self.uncertain = True
            raise WebXiError(
                "Identify outcome uncertain; no retry sent. Inspect SLM, refresh and re-arm."
            ) from None

    def navigate_measurement_screen(self, direction: str, *, screen_confirmed: bool = False):
        """Supervised preview capture only; caller must inspect the current measurement screen.

        Arrow keys can edit settings in menus. This deliberately has no generic menu,
        hold/repeat, keyboard shortcut or automatic navigation interface.
        """
        require_allowed("screen_navigation")
        action = {"up": "KeyUp", "down": "KeyDown", "left": "KeyLeft", "right": "KeyRight"}.get(
            direction
        )
        if not action:
            raise ValueError("Only single up/down/left/right arrows are supported.")
        return self._screen_key(action, screen_confirmed=screen_confirmed)

    def open_screen_menu(self, *, screen_confirmed=False):
        """Open the menu once from an acknowledged measurement view; lock all keys afterward."""
        require_allowed("open_screen_menu")
        try:
            return self._screen_key("KeyMenu", screen_confirmed=screen_confirmed)
        finally:
            self.navigation_ready = False

    def _screen_key(self, action, *, screen_confirmed):
        if (
            not self.armed
            or self.uncertain
            or not self.navigation_ready
            or not screen_confirmed
            or action not in self.actions
        ):
            raise PermissionError(
                "Inspect the measurement screen, confirm navigation and arm a supported arrow."
            )
        before = self.get(STATE)
        if before not in {"Activated", "Running", "Paused"}:
            raise PermissionError("Screen navigation blocked in this instrument state.")
        try:
            with self.session.put(
                self.address + APPLICATION,
                params={"Action": action, **({"password": self.password} if self.password else {})},
                data=b"",
                timeout=self.timeout,
                allow_redirects=False,
            ) as reply:
                if reply.status_code != 200:
                    raise WebXiError("Arrow was not acknowledged.")
            if self.get(STATE) != before:
                raise WebXiError("Instrument state changed during navigation.")
        except Exception:
            self.armed = False
            self.navigation_ready = False
            self.uncertain = True
            raise WebXiError(
                "Navigation outcome uncertain; no retry sent. Inspect the instrument."
            ) from None

    def refresh_control_state(self) -> str:
        state = self.get(STATE)
        if not isinstance(state, str):
            raise WebXiError("Unknown measurement state.")
        self.uncertain = False
        return state

    def _settle_control_state(self, state, pending):
        """Brief read-only settling; never resend the state-changing action."""
        deadline = time.monotonic() + 2.0
        for _ in range(8):
            if state not in pending or time.monotonic() >= deadline:
                break
            time.sleep(0.1)
            state = self.get(STATE)
        return state

    def measurement_action(self, action: str, *, confirmations: int = 0) -> str:
        operation = {"StartPause": "start_pause", "Stop": "stop_measurement"}.get(action, "unknown")
        require_allowed(operation)
        if not self.armed or action not in self.actions:
            raise PermissionError(
                "Arm SLM controls and verify the action is supported before using it."
            )
        if self.uncertain:
            raise PermissionError(
                "Previous action outcome is uncertain. Refresh control state before a deliberate new action."
            )
        before = self._settle_control_state(self.get(STATE), {"Stopping", "RampingDown"})
        allowed = (
            {"Activated", "Running", "Paused", "ResultMeasured"}
            if action == "StartPause"
            else {"Running", "Paused", "WaitingForTrigger"}
        )
        if before in {"Stopping", "RampingDown"}:
            raise PermissionError(
                "The SLM is still finishing its previous action. Wait briefly, then press again; no command was sent."
            )
        if action == "Stop" and before in {"Activated", "ResultMeasured"}:
            return before  # Already stopped: harmless no-op, not another instrument write.
        if before not in allowed:
            raise PermissionError(
                f"{action} is unavailable in SLM state {before!r}. "
                "No command was sent; leave loaded-result/settings views on the instrument first."
            )
        try:
            # Exactly one PUT. Never retry a toggle after any ambiguous response.
            with self.session.put(
                self.address + APPLICATION,
                params={"Action": action, **({"password": self.password} if self.password else {})},
                data=b"",
                timeout=self.timeout,
                allow_redirects=False,
            ) as reply:
                if reply.status_code != 200:
                    raise WebXiError("Instrument did not acknowledge the action.")
            after = self.get(STATE)
            expected = (
                {"Paused"}
                if action == "StartPause" and before == "Running"
                else (
                    {"Running", "WaitingForTrigger"}
                    if action == "StartPause"
                    else {"Stopping", "ResultMeasured", "Activated"}
                )
            )
            after = self._settle_control_state(
                after, ({before, "RampingDown", "Stopping"} - expected)
            )
            if after not in expected:
                raise WebXiError("Read-back has not confirmed the requested state.")
            return str(after)
        except Exception:
            self.uncertain = True
            self.armed = False
            raise WebXiError(
                "Action outcome uncertain; no retry was sent. Refresh control state, inspect the SLM, and re-arm before another deliberate action."
            ) from None

    def probe(self) -> dict:
        result = {
            "captured_utc": datetime.now(UTC).isoformat(),
            "address": self.address,
            "origin": "instrument",
            "read_only": True,
            "responses": {},
            "errors": {},
        }
        # Root is required; optional endpoints retain failures without inventing capability support.
        result["responses"][ROOT] = self.get(ROOT)
        for path in (DEVICE, STATE, OUTPUTS, SETUP, LAF):
            try:
                result["responses"][path] = self.get(path, recursive=path == DEVICE)
            except WebXiError as exc:
                result["errors"][path] = str(exc)
        try:
            result["responses"][LAF + "?metadata"] = self.get(LAF, metadata=True)
        except WebXiError as exc:
            result["errors"][LAF + "?metadata"] = str(exc)
        return result

    def read(self) -> Sample:
        state = self.get(STATE)
        if not isinstance(state, str):
            raise WebXiError("Unexpected SLM state format; capture the read-only probe first.")
        # Read descriptors/setup for each snapshot so changes made on the SLM cannot
        # silently give a spectrum the previous range or percentile interpretation.
        setup = self.get(SETUP, recursive=True)
        sequences = self.get(SEQUENCES, recursive=True)
        raw = self.get(OUTPUTS, recursive=True)
        if not all(isinstance(v, dict) for v in (setup, sequences, raw)):
            raise WebXiError("Unexpected measurement tree format.")
        if time.monotonic() - self.capabilities_at > 30:
            self.setup_metadata = self.get(SETUP, recursive=True, metadata=True)
            if not isinstance(self.setup_metadata, dict):
                raise WebXiError("Unexpected setup metadata format.")
            self.capabilities_at = time.monotonic()
        self.setup, self.sequences = setup, sequence_index(sequences)
        values, spectra = decode_outputs(raw, self.sequences, setup)
        # Fail closed if measurement setup changes while the snapshot is read.
        after = self.get(SETUP, recursive=True)
        keys = (
            "FrequencyRange",
            "FrequencyCPBBandwidth",
            "FrequencyCPBBandwidth2nd",
            "BBStatisticsBasedOn",
            *(f"StatisticsPercentile{i}" for i in range(1, 6)),
        )
        if any(setup.get(k) != after.get(k) for k in keys):
            raise WebXiError(
                "Measurement setup changed during read; waiting for a stable snapshot."
            )
        metadata = metadata_snapshot(raw, setup, self.setup_metadata)
        if self.health_groups and time.monotonic() - self.health_at > 5:
            self.health = {}
            observed = datetime.now(UTC).isoformat()
            for group in sorted(self.health_groups):
                path = {"Battery": BATTERY, "Disks": DISKS}[group]
                try:
                    if group not in self.health_definitions:
                        self.health_definitions[group] = self.get(
                            path, recursive=True, metadata=True
                        )
                    health_values = self.get(path, recursive=True)
                    self.health.update(
                        device_health_fields(
                            health_values, self.health_definitions[group], group, observed
                        )
                    )
                except WebXiError:
                    self.health[f"Device.{group}"] = {
                        "value": None,
                        "raw": None,
                        "access": "Read-only device status",
                        "description": "Status read unavailable; no previous value reused.",
                    }
            self.health_at = time.monotonic()
        metadata.update(self.health)
        return Sample(
            datetime.now(UTC),
            time.monotonic() - self.started,
            state,
            "instrument",
            values,
            {
                **raw,
                "_hbkg_context": {
                    "sequences": self.sequences,
                    "metadata": metadata,
                    "setup_basis": {k: setup.get(k) for k in keys},
                },
            },
            "pc-receipt-time; polled SLM outputs; not an atomic stream snapshot",
            spectra,
            metadata,
            self.sequences,
        )

    def close(self) -> None:
        self.session.close()
