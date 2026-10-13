"""Durable local samples. Owned by the acquisition worker, never shared across threads."""

import json
import sqlite3
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from bnkg import __version__
from bnkg.core.parameters import Sample
from bnkg.core.report_context import context_metadata


class SessionStore:
    def __init__(self, path: Path, origin: str, *, report_context=None) -> None:
        local_metadata = context_metadata(report_context) if report_context is not None else {}
        path.parent.mkdir(parents=True, exist_ok=True)
        # Exclusive reservation prevents accidentally appending to someone else's session.
        with path.open("xb"):
            pass
        self.path = path
        self.connection = sqlite3.connect(path)
        self.closed = False
        self.count = 0
        self.connection.executescript("""
            PRAGMA user_version = 1;
            CREATE TABLE metadata (key TEXT PRIMARY KEY, value TEXT NOT NULL);
            CREATE TABLE samples (
                id INTEGER PRIMARY KEY, timestamp TEXT NOT NULL, elapsed_s REAL NOT NULL,
                state TEXT NOT NULL, origin TEXT NOT NULL, quality TEXT NOT NULL,
                values_json TEXT NOT NULL, raw_json TEXT NOT NULL
            );
            CREATE TABLE events (timestamp TEXT NOT NULL, kind TEXT NOT NULL, detail TEXT NOT NULL);
        """)
        metadata = {
            "session_id": str(uuid4()),
            "app_version": __version__,
            "origin": origin,
            "started_utc": datetime.now(UTC).isoformat(),
            "schema_version": "1",
            "timestamp_basis": "PC UTC receipt time; not an instrument clock",
            "elapsed_basis": "demo measurement time or PC connection elapsed time",
            "validation": "Synthetic demo"
            if origin == "simulation"
            else "PC receipt timestamps; instrument values require measurement acceptance",
        }
        metadata.update(local_metadata)
        self.connection.executemany("INSERT INTO metadata VALUES (?, ?)", metadata.items())
        self.connection.commit()

    def append(self, sample: Sample) -> None:
        with self.connection:
            if self.count == 0 and sample.descriptors:
                self.connection.execute(
                    "INSERT OR REPLACE INTO metadata VALUES(?, ?)",
                    (
                        "parameter_basis",
                        "Device sequence descriptors and setup retained in each raw_values._hbkg_context; raw * Scale + Offset; LN aliases follow configured percentile slots. Unknown/invalid results are null.",
                    ),
                )
            self.connection.execute(
                "INSERT INTO samples(timestamp,elapsed_s,state,origin,quality,values_json,raw_json) "
                "VALUES(?,?,?,?,?,?,?)",
                (
                    sample.timestamp.isoformat(),
                    sample.elapsed_s,
                    sample.state,
                    sample.origin,
                    sample.quality,
                    json.dumps(sample.values, allow_nan=False),
                    json.dumps(sample.raw_values, allow_nan=False),
                ),
            )
        self.count += 1

    def event(self, kind: str, detail: str) -> None:
        with self.connection:
            self.connection.execute(
                "INSERT INTO events VALUES(?,?,?)", (datetime.now(UTC).isoformat(), kind, detail)
            )

    def close(self) -> None:
        if not self.closed:
            try:
                with self.connection:
                    self.connection.execute(
                        "INSERT OR REPLACE INTO metadata VALUES(?,?)",
                        ("closed_utc", datetime.now(UTC).isoformat()),
                    )
            finally:
                self.connection.close()
                self.closed = True
