"""Tipos compartidos por las fuentes, el pipeline y el detector."""

from __future__ import annotations

import math
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class CSIFrame:
    """Una observación de CSI.

    `amplitudes` y `phases` tienen una entrada por subportadora. `phases` puede
    faltar cuando la fuente no la mide (por ejemplo, el modo RSSI).
    """

    timestamp: float
    rssi: float
    amplitudes: tuple[float, ...]
    phases: tuple[float, ...] | None = None
    node_id: str = "sim-0"

    def __post_init__(self) -> None:
        if not math.isfinite(self.timestamp):
            raise ValueError("timestamp must be finite")
        if not math.isfinite(self.rssi):
            raise ValueError("rssi must be finite")
        if not self.node_id:
            raise ValueError("node_id must be non-empty")
        if self.phases is not None and len(self.phases) != len(self.amplitudes):
            raise ValueError("phases and amplitudes must have the same length")

    @property
    def n_subcarriers(self) -> int:
        return len(self.amplitudes)
