"""Almacenamiento local. T-10 usa memoria; T-12 lo pasa a SQLite."""

from wifi_sonar.storage.memory import MemoryStore

__all__ = ["MemoryStore"]
