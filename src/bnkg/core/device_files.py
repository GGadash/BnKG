"""GET-only directory inventory; never invokes the instrument Open action."""

import hashlib
import os
import time
from datetime import datetime
from pathlib import Path
from urllib.parse import quote
from uuid import uuid4

import requests

from bnkg.core.webxi import APPLICATION, WebXiClient, WebXiError

DATA = APPLICATION + "/Data"


class DeviceFilesClient(WebXiClient):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.directories = {DATA}
        self.files = {}

    def directory(self, path):
        if path not in self.directories:
            raise ValueError("Directory was not advertised by the connected SLM.")
        tree = self._request_json(path, metadata=True)
        if not isinstance(tree, dict) or "Directory" not in flags(tree):
            raise WebXiError("This firmware did not advertise a readable data directory.")
        if len(tree) > 10001 or len(self.directories) + len(self.files) > 50000:
            raise WebXiError(
                "Inventory size limit reached. Reconnect and browse a narrower folder."
            )
        entries = []
        for name, node in tree.items():
            if name == "Metadata" or not isinstance(node, dict):
                continue
            if (
                not name
                or name in {".", ".."}
                or any(c in name for c in "/\\%?#")
                or any(ord(c) < 32 for c in name)
            ):
                raise WebXiError("Unsafe directory entry refused.")
            kind = (
                "Directory"
                if "Directory" in flags(node)
                else "File"
                if "File" in flags(node)
                else ""
            )
            if not kind:
                continue
            child = path + "/" + quote(name, safe="$")
            if kind == "Directory":
                self.directories.add(child)
            elif "WriteOnly" not in flags(node):
                self.files[child] = {"name": name, "metadata": node.get("Metadata", {})}
            entries.append((name, kind, child))
        return sorted(entries, reverse=True)

    def download(
        self,
        path,
        target,
        *,
        max_bytes=256 * 1024 * 1024,
        cancelled=lambda: False,
        progress=lambda received, total: None,
    ):
        """GET one advertised file (official protocol 7.1); never Open/GetArchive/Delete."""
        if path not in self.files or not path.startswith(DATA + "/"):
            raise ValueError("File was not advertised by the connected SLM.")
        if not 1 <= max_bytes <= 256 * 1024 * 1024:
            raise ValueError("Download limit must be between 1 byte and 256 MiB.")
        target = Path(target).resolve()
        if target.exists():
            raise FileExistsError("Choose a new filename; existing files are preserved.")
        if cancelled():
            raise WebXiError("Download cancelled.")
        temporary = target.with_name("." + target.name + "." + uuid4().hex + ".partial")
        deadline = time.monotonic() + 120
        total, received = None, 0
        digest = hashlib.sha256()
        try:
            with self.session.get(
                self.address + path,
                timeout=self.timeout,
                stream=True,
                allow_redirects=False,
                headers={"Accept-Encoding": "identity"},
                params={"password": self.password} if self.password else None,
            ) as reply:
                if reply.status_code != 200:
                    raise WebXiError(
                        "File download refused: expected a complete HTTP 200 response; redirects/partial responses are not accepted."
                    )
                if reply.headers.get("Content-Encoding", "identity").lower() not in {
                    "",
                    "identity",
                }:
                    raise WebXiError("Encoded download refused; original file bytes are required.")
                length = reply.headers.get("Content-Length")
                if length is not None:
                    try:
                        total = int(length)
                    except ValueError as exc:
                        raise WebXiError("Invalid advertised file length.") from exc
                    if not 0 <= total <= max_bytes:
                        raise WebXiError("File exceeds the 256 MiB (or requested) download limit.")
                last_notice = 0
                with temporary.open("xb") as output:
                    for chunk in reply.iter_content(chunk_size=65536):
                        if cancelled():
                            raise WebXiError("Download cancelled.")
                        if time.monotonic() > deadline:
                            raise WebXiError("Download exceeded the 120-second time limit.")
                        received += len(chunk)
                        if received > max_bytes:
                            raise WebXiError("Download size limit exceeded.")
                        output.write(chunk)
                        digest.update(chunk)
                        now = time.monotonic()
                        if now - last_notice >= 0.1:
                            progress(received, total)
                            last_notice = now
                    output.flush()
                    os.fsync(output.fileno())
                if total is not None and received != total:
                    raise WebXiError(
                        "Incomplete file: received size does not match Content-Length."
                    )
                if cancelled() or time.monotonic() > deadline:
                    raise WebXiError("Download cancelled or timed out before completion.")
                # Atomic, no-overwrite publication on both Windows and Linux.
                os.link(temporary, target)
                return {"path": str(target), "bytes": received, "sha256": digest.hexdigest()}
        except requests.RequestException:
            raise WebXiError(
                "Download failed (connection, timeout or access). No complete file was published."
            ) from None
        finally:
            if temporary.exists():
                temporary.unlink()

    def latest(self, limit, start=None, end=None, cancelled=lambda: False):
        result = []
        deadline = time.monotonic() + 60
        reads = 0
        dates = self.directory(DATA)
        for name, kind, path in dates:
            if cancelled():
                raise WebXiError("Cancelled.")
            if kind != "Directory":
                continue
            try:
                day = datetime.strptime(name, "%Y_%m_%d").date()
            except ValueError:
                continue  # Non-date folders remain accessible in Browse all.
            if (start and day < start) or (end and day > end):
                continue
            if len(result) >= limit:
                break
            reads += 1
            if reads > 200 or time.monotonic() > deadline:
                raise WebXiError(
                    "Search limit reached. Narrow the date range or use Browse all folders."
                )
            records = self.directory(path)
            result.extend(records[: limit - len(result)])
        return result


def flags(node):
    metadata = node.get("Metadata", {})
    return (
        {v.strip() for v in str(metadata.get("Flags", "")).split(",")}
        if isinstance(metadata, dict)
        else set()
    )
