"""A CSISource backed by frames already in memory."""

from collections.abc import Iterator, Sequence

from wifi_sonar.sources.frame import CSIFrame


class ListedSource:
    def __init__(self, frames: Sequence[CSIFrame]) -> None:
        self._frames = tuple(frames)

    def frames(self) -> Iterator[CSIFrame]:
        return iter(self._frames)
