"""User-initiated bounded LAN discovery. No configuration writes or automatic scans."""

import ipaddress
import socket
import subprocess
import sys
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass

from zeroconf import IPVersion, ServiceBrowser, ServiceListener, Zeroconf

from bnkg.core.webxi import DEVICE, ROOT, WebXiClient

SERVICE = "_web-xi._tcp.local."


@dataclass(frozen=True)
class DiscoveredDevice:
    address: str
    name: str
    status: str
    method: str


def subnet_hosts(value: str) -> list[str]:
    network = ipaddress.ip_network(value.strip(), strict=False)
    private_ranges = [
        ipaddress.ip_network(v)
        for v in ("10.0.0.0/8", "172.16.0.0/12", "192.168.0.0/16", "169.254.0.0/16")
    ]
    if network.version != 4 or not any(network.subnet_of(n) for n in private_ranges):
        raise ValueError("Choose a private/local IPv4 subnet, such as 192.168.1.0/24.")
    if network.num_addresses > 256:
        raise ValueError("Scan one /24 or smaller subnet at a time (at most 254 hosts).")
    return [str(ip) for ip in network.hosts()]


def identify_address(address: str, method: str) -> DiscoveredDevice | None:
    client = WebXiClient(address, timeout=(0.4, 0.6))
    try:
        root = client.get(ROOT)
        if not isinstance(root, dict) or not any(k.lower() == "device" for k in root):
            return None
        identity = client.get(DEVICE, recursive=True)
        if not isinstance(identity, dict):
            return None
        family = identity.get("Family", "")
        name = str(identity.get("HostName") or identity.get("Id") or "Web-XI device")[:160]
        status = "SLM identified" if family == "SLM" else "Web-XI; check device type"
        return DiscoveredDevice(address, name, status, method)
    except Exception:
        return None
    finally:
        client.close()


class _Listener(ServiceListener):
    def __init__(self):
        self.lock = threading.Lock()
        self.names: set[str] = set()

    def add_service(self, zc, service_type, name):
        with self.lock:
            if len(self.names) < 256:
                self.names.add(name)

    def update_service(self, zc, service_type, name):
        self.add_service(zc, service_type, name)

    def remove_service(self, zc, service_type, name):
        with self.lock:
            self.names.discard(name)


def discover_mdns(cancel: threading.Event, emit, progress, seconds: float = 5.0):
    listener = _Listener()
    with Zeroconf(ip_version=IPVersion.V4Only) as zc:
        browser = ServiceBrowser(zc, SERVICE, listener)
        try:
            progress("Listening for Web-XI advertisements on the local network…")
            cancel.wait(seconds)
            with listener.lock:
                names = sorted(listener.names)
            for name in names:
                if cancel.is_set():
                    break
                info = zc.get_service_info(SERVICE, name, timeout=500)
                if not info:
                    continue
                for address in info.parsed_addresses(IPVersion.V4Only):
                    if cancel.is_set():
                        break
                    endpoint = address if info.port == 80 else f"{address}:{info.port}"
                    found = identify_address(endpoint, "mDNS")
                    # A protected meter can advertise even when its JSON requires a password.
                    emit(
                        found
                        or DiscoveredDevice(
                            endpoint,
                            info.server.rstrip("."),
                            "Advertised Web-XI; access unverified",
                            "mDNS",
                        )
                    )
        finally:
            browser.cancel()


def _scan_host(address: str, cancel: threading.Event) -> DiscoveredDevice | None:
    if cancel.is_set():
        return None
    http_open = False
    try:
        with socket.create_connection((address, 80), timeout=0.3):
            http_open = True
    except OSError:
        pass
    if http_open:
        identified = identify_address(address, "Subnet")
        return identified or DiscoveredDevice(
            address, "", "HTTP response; not identified as SLM", "Subnet"
        )
    if cancel.is_set():
        return None
    if sys.platform == "win32":
        try:
            result = subprocess.run(
                ["ping", "-n", "1", "-w", "350", address],
                capture_output=True,
                timeout=1.5,
                creationflags=subprocess.CREATE_NO_WINDOW,
            )
            # Windows can return exit 0 for destination-unreachable; require an actual TTL reply.
            if result.returncode == 0 and b"ttl=" in result.stdout.lower():
                return DiscoveredDevice(
                    address, "", "Ping response; no Web-XI identification", "Subnet"
                )
        except (OSError, subprocess.TimeoutExpired):
            pass
    return None


def scan_subnet(value: str, cancel: threading.Event, emit, progress):
    hosts = subnet_hosts(value)
    with ThreadPoolExecutor(max_workers=12, thread_name_prefix="BnKG-discovery") as pool:
        futures = [pool.submit(_scan_host, host, cancel) for host in hosts]
        for count, future in enumerate(as_completed(futures), 1):
            if cancel.is_set():
                for queued in futures:
                    queued.cancel()
                break
            result = future.result()
            if result:
                emit(result)
            progress(f"Checked {count}/{len(hosts)} addresses. Some devices may block replies.")
