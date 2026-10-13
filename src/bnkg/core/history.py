"""Bounded read-only access to BnKG v1 logs; no device or acquisition dependencies."""

import json
import sqlite3
import time
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path

from bnkg.core.measurements import decode_outputs
from bnkg.core.spectrum import SpectrumFrame, finite

PAGE_SIZE = 100
JSON_LIMIT = 2_000_000


@dataclass(frozen=True)
class HistoryRow:
    id: int
    timestamp: str
    elapsed: float | None
    state: str
    origin: str
    quality: str
    laf: float | None
    laeq: float | None
    values: tuple = ()


@dataclass(frozen=True)
class HistoryPage:
    path: str
    metadata: tuple
    rows: tuple[HistoryRow, ...]
    ceiling: int
    previous: bool
    following: bool


@dataclass(frozen=True)
class SavedSample:
    label: str
    row: HistoryRow
    values: tuple
    frame: SpectrumFrame | None
    explanation: str


def object_json(text, limit=JSON_LIMIT):
    if not isinstance(text, str) or len(text) > limit:
        raise ValueError("Saved JSON exceeds the supported size.")
    try:
        obj = json.loads(text)
    except (ValueError, RecursionError) as exc:
        raise ValueError("Saved row contains malformed JSON.") from exc
    if not isinstance(obj, dict):
        raise ValueError("Saved JSON must be an object.")
    return obj


@contextmanager
def open_history(path, cancelled=lambda: False, expected_session=None):
    path = Path(path).resolve()
    if not path.is_file():
        raise ValueError("Select an existing BnKG SQLite session.")
    deadline = time.monotonic() + 4
    if cancelled():
        raise ValueError("History read cancelled.")
    db = sqlite3.connect(path.as_uri() + "?mode=ro", uri=True, timeout=0.25)
    try:
        db.setlimit(sqlite3.SQLITE_LIMIT_LENGTH, JSON_LIMIT + 65536)
        db.setlimit(sqlite3.SQLITE_LIMIT_SQL_LENGTH, 16384)
        db.set_progress_handler(lambda: int(cancelled() or time.monotonic() > deadline), 1000)
        db.execute("PRAGMA query_only=ON")
        db.execute("PRAGMA trusted_schema=OFF")
        db.execute("BEGIN")
        if db.execute("PRAGMA user_version").fetchone()[0] != 1:
            raise ValueError("Unsupported session schema. Original file is unchanged.")
        objects = dict(
            db.execute("SELECT name,type FROM sqlite_master WHERE name IN ('samples','metadata')")
        )
        if objects != {"samples": "table", "metadata": "table"}:
            raise ValueError("Not a supported BnKG session (required tables missing).")
        columns = {r[1]: r for r in db.execute("PRAGMA table_info(samples)")}
        if (
            not {
                "id",
                "timestamp",
                "elapsed_s",
                "state",
                "origin",
                "quality",
                "values_json",
                "raw_json",
            }
            <= columns.keys()
            or columns["id"][2].upper() != "INTEGER"
            or columns["id"][5] != 1
        ):
            raise ValueError("Unsupported sample table layout.")
        meta_rows = db.execute("SELECT key,value FROM metadata LIMIT 129").fetchall()
        if len(meta_rows) > 128 or any(
            not isinstance(v, str) or len(v) > 16384 for row in meta_rows for v in row
        ):
            raise ValueError("Session metadata exceeds the supported limits.")
        metadata = dict(meta_rows)
        if not metadata.get("session_id") or "origin" not in metadata:
            raise ValueError("Session identity/origin metadata is missing.")
        if expected_session is not None and expected_session != metadata["session_id"]:
            raise ValueError("The session file changed. Open it again before browsing.")
        yield db, metadata
        if cancelled():
            raise ValueError("History read cancelled.")
    except sqlite3.Error as exc:
        raise ValueError(
            "Session read failed: unsupported, corrupt, locked, oversized or cancelled database."
        ) from exc
    finally:
        db.close()


def summary(record):
    ident, timestamp, elapsed, state, origin, quality, encoded = record
    try:
        values = object_json(encoded, 65536)
    except ValueError:
        values = {}
        quality = str(quality) + "; invalid/oversized saved values"
    return HistoryRow(
        ident,
        str(timestamp),
        elapsed if finite(elapsed) else None,
        str(state),
        str(origin),
        str(quality),
        values.get("LAF") if finite(values.get("LAF")) else None,
        values.get("LAeq") if finite(values.get("LAeq")) else None,
        tuple((k, v if finite(v) else None) for k, v in values.items()),
    )


def read_page(
    path, *, after=0, before=None, ceiling=None, expected_session=None, cancelled=lambda: False
):
    with open_history(path, cancelled, expected_session) as (db, metadata):
        if ceiling is None:
            ceiling = db.execute("SELECT coalesce(max(id),0) FROM samples").fetchone()[0]
        fields = "id,substr(timestamp,1,128),elapsed_s,substr(state,1,128),substr(origin,1,64),substr(quality,1,2048),CASE WHEN length(values_json)<=65536 THEN values_json ELSE 'oversized' END"
        if before is None:
            records = db.execute(
                f"SELECT {fields} FROM samples WHERE id>? AND id<=? ORDER BY id LIMIT ?",
                (after, ceiling, PAGE_SIZE),
            ).fetchall()
        else:
            records = db.execute(
                f"SELECT {fields} FROM samples WHERE id<? AND id<=? ORDER BY id DESC LIMIT ?",
                (before, ceiling, PAGE_SIZE),
            ).fetchall()[::-1]
        rows = tuple(summary(r) for r in records)
        previous = bool(
            rows
            and db.execute("SELECT 1 FROM samples WHERE id<? LIMIT 1", (rows[0].id,)).fetchone()
        )
        following = bool(
            rows
            and db.execute(
                "SELECT 1 FROM samples WHERE id>? AND id<=? LIMIT 1", (rows[-1].id, ceiling)
            ).fetchone()
        )
        return HistoryPage(
            str(Path(path).resolve()), tuple(metadata.items()), rows, ceiling, previous, following
        )


def read_sample(path, ident, *, expected_session=None, cancelled=lambda: False):
    with open_history(path, cancelled, expected_session) as (db, metadata):
        record = db.execute(
            "SELECT id,timestamp,elapsed_s,state,origin,quality,values_json,raw_json FROM samples WHERE id=?",
            (ident,),
        ).fetchone()
        if record is None:
            raise ValueError("Saved sample no longer exists; refresh the session.")
        row = summary(record[:7])
        values = object_json(record[6], 65536)
        if len(values) > 512:
            raise ValueError("Too many saved parameters; supported limit is 512.")
        raw = object_json(record[7])
        frame = None
        explanation = "No supported spectrum: this row lacks retained device descriptors. Recorded scalar values remain available."
        context = raw.get("_hbkg_context")
        if row.origin != "instrument" or metadata["origin"] != "instrument":
            explanation = "Synthetic or unknown-origin session: browse recorded values here; instrument Frequency does not accept simulation."
        elif isinstance(context, dict) and isinstance(context.get("sequences"), dict):
            sequences = context["sequences"]
            setup = context.get("setup_basis", {})
            if not isinstance(setup, dict) or any(
                not isinstance(d, dict) for d in sequences.values()
            ):
                raise ValueError("Malformed saved descriptor context; no reconstruction attempted.")
            try:
                # This row's raw values and descriptors, never the current instrument setup.
                broadband, spectra = decode_outputs(raw, sequences, setup)
                measurement = context.get("metadata", {})
                if not isinstance(measurement, dict):
                    raise ValueError("Malformed saved measurement metadata.")
                frame = SpectrumFrame.capture(
                    spectra,
                    broadband=broadband,
                    timestamp=row.timestamp,
                    state=row.state,
                    quality=row.quality,
                    measurement={
                        k: measurement[k]
                        for k in ("MeasurementCounter", "StartTime", "StopTime", "ElapsedTime")
                        if k in measurement
                    },
                )
            except (TypeError, ValueError, OverflowError, RecursionError) as exc:
                raise ValueError("Unsupported or malformed saved measurement context.") from exc
            if not frame.series:
                frame = None
                explanation = "No supported CPB spectrum retained in this row. No bands or weighting values were synthesized."
            else:
                explanation = "Reconstructed from this saved row's direct raw SLM outputs and descriptors. PC receipt time; not an atomic stream snapshot."
        label = f"{Path(path).name} · sample {ident} · session {metadata['session_id']}"
        return SavedSample(label, row, tuple(values.items()), frame, explanation)
