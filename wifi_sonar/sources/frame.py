"""CSI observation shared by every source."""

from dataclasses import dataclass

import numpy as np


@dataclass
class CSIFrame:
    """One CSI observation.

    ``amplitudes`` has one value per subcarrier. ``phases`` is optional and uses
    the same length when present. The product estimates presence and motion in
    the operator's own home; a frame does not identify a person.
    """

    timestamp: float
    rssi: float
    amplitudes: np.ndarray
    phases: np.ndarray | None
    node_id: str

    def __post_init__(self) -> None:
        self.amplitudes = np.asarray(self.amplitudes, dtype=np.float64)
        if self.amplitudes.ndim != 1:
            raise ValueError("amplitudes must be a 1-D array of subcarriers")
        if self.phases is not None:
            self.phases = np.asarray(self.phases, dtype=np.float64)
            if self.phases.shape != self.amplitudes.shape:
                raise ValueError("phases must match amplitudes length")

    @property
    def n_subcarriers(self) -> int:
        return int(self.amplitudes.shape[0])
