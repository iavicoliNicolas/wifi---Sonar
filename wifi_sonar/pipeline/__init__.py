"""Ingestion helpers that do not care which ``CSISource`` produced the frames."""

from collections.abc import Iterator

from wifi_sonar.sources.base import CSISource
from wifi_sonar.sources.frame import CSIFrame


def collect(source: CSISource) -> list[CSIFrame]:
    """Read a source to completion. Simulator and replay both go through here."""
    return list(iter_source(source))


def iter_source(source: CSISource) -> Iterator[CSIFrame]:
    return source.frames()
