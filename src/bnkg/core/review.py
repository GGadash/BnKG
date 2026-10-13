"""Local review annotations: bounded, verified sidecars; source sessions stay read-only."""

import hashlib
import json
import os
import tempfile
import time
from dataclasses import asdict, dataclass, replace
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from bnkg.core.history import open_history

KINDS = ("M1", "M2", "M3", "Exclude")
MAX_MARKERS = 128
MAX_REFERENCES = 1000
MAX_BYTES = 1_000_000
BASIS = "Local review labels only; no samples removed and no acoustic quantities recalculated. PC receipt times are not integration intervals."


@dataclass(frozen=True)
class RowReference:
    id: int
    timestamp: str
    origin: str
    sha256: str


@dataclass(frozen=True)
class Marker:
    id: str
    kind: str
    note: str
    created_utc: str
    rows: tuple[RowReference, ...]


@dataclass(frozen=True)
class Review:
    session_id: str
    origin: str
    markers: tuple[Marker, ...] = ()


def text(value, limit):
    if not isinstance(value, str) or len(value) > limit or "\x00" in value:
        raise ValueError("Invalid or oversized review text.")
    return value


def decode(payload):
    if (
        not isinstance(payload, dict)
        or payload.get("format") != "bnkg-review"
        or type(payload.get("version")) is not int
        or payload["version"] != 1
        or payload.get("basis") != BASIS
    ):
        raise ValueError("Unsupported review format or measurement basis.")
    session = text(payload.get("session_id"), 16384)
    origin = text(payload.get("origin"), 64)
    entries = payload.get("markers")
    if not session or not isinstance(entries, list) or len(entries) > MAX_MARKERS:
        raise ValueError("Review must have a session identity and at most 128 markers.")
    markers, marker_ids, count = [], set(), 0
    for entry in entries:
        if not isinstance(entry, dict):
            raise ValueError("Malformed review marker.")
        ident = text(entry.get("id"), 64)
        kind = entry.get("kind")
        if not ident or ident in marker_ids or kind not in KINDS:
            raise ValueError("Unknown marker kind or duplicate marker identity.")
        marker_ids.add(ident)
        created = text(entry.get("created_utc"), 64)
        try:
            stamp = datetime.fromisoformat(created)
            if stamp.tzinfo is None or stamp.utcoffset().total_seconds() != 0:
                raise ValueError()
        except (ValueError, OverflowError) as exc:
            raise ValueError("Marker creation time must be UTC.") from exc
        rows = entry.get("rows")
        if not isinstance(rows, list) or not 1 <= len(rows) <= 100:
            raise ValueError("Each marker needs 1 to 100 exact saved rows.")
        refs, last = [], 0
        for row in rows:
            if (
                not isinstance(row, dict)
                or type(row.get("id")) is not int
                or not last < row["id"] <= 9223372036854775807
            ):
                raise ValueError("Marker row IDs must be positive and ordered.")
            last = row["id"]
            digest = text(row.get("sha256"), 64)
            if len(digest) != 64 or any(c not in "0123456789abcdef" for c in digest):
                raise ValueError("Invalid row fingerprint.")
            refs.append(
                RowReference(
                    last, text(row.get("timestamp"), 128), text(row.get("origin"), 64), digest
                )
            )
        count += len(refs)
        if count > MAX_REFERENCES:
            raise ValueError("A review supports at most 1,000 row references.")
        markers.append(Marker(ident, kind, text(entry.get("note"), 500), created, tuple(refs)))
    return Review(session, origin, tuple(markers))


def encode(review):
    payload = {"format": "bnkg-review", "version": 1, "basis": BASIS, **asdict(review)}
    data = json.dumps(payload, ensure_ascii=True, allow_nan=False).encode("utf-8")
    if len(data) + 1 > MAX_BYTES:
        raise ValueError("Review exceeds 1 MB. Save a smaller review.")
    decode(json.loads(data))
    return data + b"\n"


def reference(db, ident):
    record = db.execute(
        "SELECT id,timestamp,elapsed_s,state,origin,quality,values_json,raw_json FROM samples WHERE id=?",
        (ident,),
    ).fetchone()
    if record is None:
        raise ValueError("A marked sample is missing from this session.")
    try:
        encoded = json.dumps(record, ensure_ascii=True, allow_nan=False).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise ValueError("Unsupported saved row content.") from exc
    return RowReference(
        ident, text(record[1], 128), text(record[4], 64), hashlib.sha256(encoded).hexdigest()
    )


def guard(cancelled, deadline):
    if cancelled():
        raise ValueError("Review operation cancelled.")
    if time.monotonic() > deadline:
        raise ValueError("Review verification exceeded four seconds; use a smaller review.")


def verify(db, metadata, review, cancelled, deadline):
    if metadata["session_id"] != review.session_id or metadata["origin"] != review.origin:
        raise ValueError("Review belongs to another session or origin.")
    cache = {}
    for marker in review.markers:
        for ref in marker.rows:
            guard(cancelled, deadline)
            if ref.id not in cache:
                cache[ref.id] = reference(db, ref.id)
            if cache[ref.id] != ref:
                raise ValueError(
                    f"Marked sample {ref.id} changed. Review cannot be attached to this file."
                )


def add_marker(path, *, review, ids, kind, note, expected_session, cancelled=lambda: False):
    deadline = time.monotonic() + 4
    if (
        kind not in KINDS
        or not ids
        or len(ids) > 100
        or any(type(i) is not int or i <= 0 for i in ids)
        or list(ids) != sorted(set(ids))
    ):
        raise ValueError("Select 1 to 100 saved rows in order and a supported marker kind.")
    note = text(note, 500).strip()
    with open_history(path, cancelled, expected_session) as (db, meta):
        review = review or Review(meta["session_id"], meta["origin"])
        encode(review)
        verify(db, meta, review, cancelled, deadline)
        refs = []
        for ident in ids:
            guard(cancelled, deadline)
            refs.append(reference(db, ident))
        marker = Marker(str(uuid4()), kind, note, datetime.now(UTC).isoformat(), tuple(refs))
        result = replace(review, markers=review.markers + (marker,))
        encode(result)
        return result


def read_review(path, *, target, expected_session, cancelled=lambda: False):
    deadline = time.monotonic() + 4
    with Path(target).open("rb") as handle:
        data = handle.read(MAX_BYTES + 1)
    if len(data) > MAX_BYTES:
        raise ValueError("Review file exceeds 1 MB.")
    try:
        review = decode(json.loads(data))
    except (ValueError, RecursionError, UnicodeError) as exc:
        raise ValueError("Invalid review file: " + str(exc)) from exc
    with open_history(path, cancelled, expected_session) as (db, meta):
        verify(db, meta, review, cancelled, deadline)
    return review


def save_review(path, *, target, review, expected_session, cancelled=lambda: False):
    data = encode(review)
    deadline = time.monotonic() + 4
    with open_history(path, cancelled, expected_session) as (db, meta):
        verify(db, meta, review, cancelled, deadline)
    target = Path(target).resolve()
    if target.exists():
        raise ValueError("Choose a new review filename; existing files are preserved.")
    # Publish a fully written snapshot without overwriting a racing destination.
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(
            prefix=".bnkg-review-", dir=target.parent, delete=False
        ) as handle:
            temporary = Path(handle.name)
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        guard(cancelled, deadline)
        os.link(temporary, target)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
    return str(target)
