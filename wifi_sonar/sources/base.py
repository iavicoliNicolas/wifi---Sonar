"""Interfaz común de las fuentes de CSI."""

from __future__ import annotations

from collections.abc import Iterator
from typing import Protocol, runtime_checkable

from wifi_sonar.models import CSIFrame


@runtime_checkable
class CSISource(Protocol):
    """Cualquier origen que el pipeline pueda consumir sin conocer el hardware."""

    @property
    def sample_rate_hz(self) -> float: ...

    def frames(self) -> Iterator[CSIFrame]: ...


def read_frames(source: CSISource, limit: int | None = None) -> list[CSIFrame]:
    """Materializa una fuente. El mismo helper sirve para el simulador y el replay."""

    collected: list[CSIFrame] = []
    for frame in source.frames():
        collected.append(frame)
        if limit is not None and len(collected) >= limit:
            break
    return collected
