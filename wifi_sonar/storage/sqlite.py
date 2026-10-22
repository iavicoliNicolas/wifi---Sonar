"""SQLite local para eventos, calibraciones y config."""

from __future__ import annotations

import json
import sqlite3
import threading
from datetime import UTC, datetime, timedelta
from pathlib import Path


class SqliteStore:
    def __init__(self, path: str | Path, retention_days: int = 30) -> None:
        self.path = Path(path)
        self.retention_days = retention_days
        self._lock = threading.Lock()
        if self.path.parent and str(self.path.parent) not in ("", "."):
            self.path.parent.mkdir(parents=True, exist_ok=True)
        self.migrate()

    def connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path)
        connection.row_factory = sqlite3.Row
        return connection

    def migrate(self) -> None:
        with self._lock, self.connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS schema_migrations (
                    id TEXT PRIMARY KEY
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    ts REAL NOT NULL,
                    recorded_at TEXT NOT NULL,
                    state TEXT NOT NULL,
                    score REAL NOT NULL,
                    node_id TEXT NOT NULL,
                    zone TEXT NOT NULL DEFAULT ''
                )
                """
            )
            connection.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_events_recorded_at
                ON events (recorded_at)
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS calibrations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    created_at TEXT NOT NULL,
                    payload TEXT NOT NULL
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS config (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                )
                """
            )
            connection.execute(
                "INSERT OR IGNORE INTO schema_migrations (id) VALUES (?)",
                ("001_initial",),
            )

    def add_event(self, event: dict[str, object]) -> None:
        recorded_at = str(event.get("recorded_at") or datetime.now(UTC).isoformat())
        with self._lock, self.connect() as connection:
            connection.execute(
                """
                INSERT INTO events (ts, recorded_at, state, score, node_id, zone)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    float(event["ts"]),  # type: ignore[arg-type]
                    recorded_at,
                    str(event["state"]),
                    float(event["score"]),  # type: ignore[arg-type]
                    str(event.get("node_id", "")),
                    str(event.get("zone", "")),
                ),
            )
        self.purge(self.retention_days)

    def list_events(self, limit: int = 100) -> list[dict[str, object]]:
        if limit < 1:
            return []
        with self._lock, self.connect() as connection:
            rows = connection.execute(
                """
                SELECT ts, recorded_at, state, score, node_id, zone
                FROM events
                ORDER BY id DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        return [dict(row) for row in rows]

    def save_calibration(self, payload: dict[str, object]) -> None:
        created_at = str(payload.get("created_at") or datetime.now(UTC).isoformat())
        with self._lock, self.connect() as connection:
            connection.execute(
                "INSERT INTO calibrations (created_at, payload) VALUES (?, ?)",
                (created_at, json.dumps(payload)),
            )

    def load_calibration(self) -> dict[str, object] | None:
        with self._lock, self.connect() as connection:
            row = connection.execute(
                "SELECT payload FROM calibrations ORDER BY id DESC LIMIT 1"
            ).fetchone()
        if row is None:
            return None
        return json.loads(row["payload"])

    def save_config(self, payload: dict[str, object]) -> None:
        with self._lock, self.connect() as connection:
            connection.execute(
                """
                INSERT INTO config (key, value) VALUES ('app', ?)
                ON CONFLICT(key) DO UPDATE SET value = excluded.value
                """,
                (json.dumps(payload),),
            )

    def load_config(self) -> dict[str, object] | None:
        with self._lock, self.connect() as connection:
            row = connection.execute("SELECT value FROM config WHERE key = 'app'").fetchone()
        if row is None:
            return None
        return json.loads(row["value"])

    def clear_events(self) -> None:
        with self._lock, self.connect() as connection:
            connection.execute("DELETE FROM events")

    def clear_all(self) -> None:
        with self._lock, self.connect() as connection:
            connection.execute("DELETE FROM events")
            connection.execute("DELETE FROM calibrations")

    def purge(self, retention_days: int | None = None, now: datetime | None = None) -> int:
        days = self.retention_days if retention_days is None else retention_days
        moment = now if now is not None else datetime.now(UTC)
        if moment.tzinfo is None:
            moment = moment.replace(tzinfo=UTC)
        cutoff = (moment - timedelta(days=days)).isoformat()
        with self._lock, self.connect() as connection:
            cursor = connection.execute(
                "DELETE FROM events WHERE recorded_at < ?",
                (cutoff,),
            )
            return int(cursor.rowcount)
