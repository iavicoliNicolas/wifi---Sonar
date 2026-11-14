"""Fuente CSI respaldada por frames que ya están en memoria."""

from __future__ import annotations

from collections.abc import Iterator, Sequence

from wifi_sonar.models import CSIFrame


class ListedSource:
    def __init__(self, frames: Sequence[CSIFrame], sample_rate_hz: float = 100.0) -> None:
        if sample_rate_hz <= 0:
            raise ValueError("sample_rate_hz must be positive")
        self._frames = tuple(frames)
        self._sample_rate_hz = sample_rate_hz

    @property
    def sample_rate_hz(self) -> float:
        return self._sample_rate_hz

    def frames(self) -> Iterator[CSIFrame]:
        return iter(self._frames)
