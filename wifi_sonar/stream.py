"""El hub se queda con el último snapshot y tira los que nadie llegó a leer."""

from __future__ import annotations

import threading


class SnapshotHub:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self.latest: dict[str, object] | None = None
        self.dropped = 0
        self._pending = False

    def publish(self, snapshot: dict[str, object]) -> None:
        with self._lock:
            if self._pending:
                self.dropped += 1
            self.latest = snapshot
            self._pending = True

    def take(self) -> dict[str, object] | None:
        with self._lock:
            if not self._pending:
                return None
            self._pending = False
            return self.latest
