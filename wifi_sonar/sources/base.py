"""Common source interface. Pipeline code depends on this, not on a concrete device."""

from collections.abc import Iterator
from typing import Protocol

from wifi_sonar.sources.frame import CSIFrame


class CSISource(Protocol):
    """Anything that yields ``CSIFrame`` values in time order."""

    def frames(self) -> Iterator[CSIFrame]:
        """Stream observations. May block when replaying in real time."""
