"""Historial, calibración y config en memoria."""

from __future__ import annotations


class MemoryStore:
    def __init__(self) -> None:
        self.events: list[dict[str, object]] = []
        self.calibration: dict[str, object] | None = None
        self.config: dict[str, object] | None = None

    def add_event(self, event: dict[str, object]) -> None:
        self.events.append(dict(event))

    def list_events(self, limit: int = 100) -> list[dict[str, object]]:
        if limit < 1:
            return []
        return list(reversed(self.events[-limit:]))

    def save_calibration(self, payload: dict[str, object]) -> None:
        self.calibration = dict(payload)

    def load_calibration(self) -> dict[str, object] | None:
        return None if self.calibration is None else dict(self.calibration)

    def save_config(self, payload: dict[str, object]) -> None:
        self.config = dict(payload)

    def load_config(self) -> dict[str, object] | None:
        return None if self.config is None else dict(self.config)

    def clear_events(self) -> None:
        self.events.clear()
