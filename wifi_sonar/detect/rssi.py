"""Coarse motion from RSSI of devices the operator already named.

Nothing here scans the LAN. Samples are either typed in by the operator or
produced by the simulator under a label they chose.
"""

from collections.abc import Sequence
from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class RSSIPoint:
    timestamp: float
    rssi: float
    device_id: str


def simulated_rssi(
    seed: int,
    duration_s: float,
    *,
    device_id: str,
    swing: bool = False,
) -> list[RSSIPoint]:
    """A coarse trace for one named device. ``swing`` is a scripted walk."""
    if duration_s <= 0:
        raise ValueError("duration_s must be positive")
    if not device_id or device_id in {"*", "scan", "all"}:
        raise ValueError("device_id must be a name you already know")
    rng = np.random.default_rng(seed)
    count = int(round(duration_s * 10))
    points: list[RSSIPoint] = []
    for index in range(count):
        timestamp = index / 10
        rssi = -62.0 + float(rng.normal(0.0, 0.35))
        if swing:
            rssi += 6.0 * float(np.sin(2.0 * np.pi * 0.5 * timestamp))
        points.append(RSSIPoint(timestamp=timestamp, rssi=rssi, device_id=device_id))
    return points


def detect_rssi(
    points: Sequence[RSSIPoint],
    *,
    window_s: float = 2.0,
    motion_db: float = 4.0,
) -> list[dict[str, object]]:
    """Empty or motion only. RSSI does not support a still-presence state."""
    if window_s <= 0 or motion_db <= 0:
        raise ValueError("window_s and motion_db must be positive")
    samples: list[dict[str, object]] = []
    for index, point in enumerate(points):
        start = point.timestamp - window_s
        window = [item.rssi for item in points[: index + 1] if item.timestamp >= start]
        span = (max(window) - min(window)) if window else 0.0
        moving = len(window) >= 5 and span >= motion_db
        score = float(np.clip(span / (motion_db * 2.0), 0.0, 1.0))
        samples.append(
            {
                "ts": point.timestamp,
                "state": "motion" if moving else "empty",
                "score": score,
                "mode": "rssi",
            }
        )
    return samples
