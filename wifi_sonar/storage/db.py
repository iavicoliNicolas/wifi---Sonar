"""SQLite for state changes, calibrations, and config. Schema version 1."""

import json
import sqlite3
import time
from pathlib import Path

from wifi_sonar.detect.calibrate import Calibration

SCHEMA = """
CREATE TABLE IF NOT EXISTS meta (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS events (
    id INTEGER PRIMARY KEY,
    ts REAL NOT NULL,
    state TEXT NOT NULL,
    score REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS calibrations (
    id INTEGER PRIMARY KEY,
    created_at REAL NOT NULL,
    payload TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS config (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    payload TEXT NOT NULL
);
"""


class Store:
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self._conn = sqlite3.connect(self.path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self.migrate()

    def migrate(self) -> None:
        self._conn.executescript(SCHEMA)
        self._conn.execute(
            "INSERT OR IGNORE INTO meta (key, value) VALUES ('schema', '1')",
        )
        self._conn.commit()

    def close(self) -> None:
        self._conn.close()

    def add_event(self, ts: float, state: str, score: float) -> None:
        self._conn.execute(
            "INSERT INTO events (ts, state, score) VALUES (?, ?, ?)",
            (ts, state, score),
        )
        self._conn.commit()

    def events(self) -> list[dict[str, object]]:
        rows = self._conn.execute("SELECT ts, state, score FROM events ORDER BY id")
        return [{"ts": row["ts"], "state": row["state"], "score": row["score"]} for row in rows]

    def save_calibration(self, calibration: Calibration, created_at: float | None = None) -> None:
        moment = time.time() if created_at is None else created_at
        payload = json.dumps(calibration.to_dict())
        self._conn.execute(
            "INSERT INTO calibrations (created_at, payload) VALUES (?, ?)",
            (moment, payload),
        )
        self._conn.commit()

    def latest_calibration(self) -> Calibration | None:
        row = self._conn.execute(
            "SELECT payload FROM calibrations ORDER BY id DESC LIMIT 1",
        ).fetchone()
        if row is None:
            return None
        return Calibration.from_dict(json.loads(row["payload"]))

    def save_config(self, payload: str) -> None:
        self._conn.execute(
            """
            INSERT INTO config (id, payload) VALUES (1, ?)
            ON CONFLICT(id) DO UPDATE SET payload = excluded.payload
            """,
            (payload,),
        )
        self._conn.commit()

    def load_config(self) -> str | None:
        row = self._conn.execute("SELECT payload FROM config WHERE id = 1").fetchone()
        if row is None:
            return None
        return str(row["payload"])

    def purge(self, retention_s: float, now: float) -> int:
        cutoff = now - retention_s
        cursor = self._conn.execute("DELETE FROM events WHERE ts < ?", (cutoff,))
        self._conn.commit()
        return int(cursor.rowcount)

    def clear(self) -> None:
        self._conn.execute("DELETE FROM events")
        self._conn.execute("DELETE FROM calibrations")
        self._conn.commit()
