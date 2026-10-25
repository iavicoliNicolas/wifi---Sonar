"""Sliding-window features over a cleaned CSI trace.

Motion energy uses the task's 2 s window. Breathing energy uses 8 s: a 2 s
window cannot separate 0.1–0.5 Hz (the bin spacing is 0.5 Hz). See D-009.
"""

from collections.abc import Sequence
from dataclasses import dataclass

import numpy as np

from wifi_sonar.sources.frame import CSIFrame

MOTION_BAND = (0.5, 5.0)
BREATHING_BAND = (0.1, 0.5)


@dataclass(frozen=True)
class WindowFeatures:
    timestamp: float
    variance: float
    mean_abs_diff: float
    motion_energy: float
    breathing_energy: float


def extract_features(
    frames: Sequence[CSIFrame],
    *,
    window_s: float = 2.0,
    step_s: float = 0.5,
    breathing_window_s: float = 8.0,
) -> list[WindowFeatures]:
    if window_s <= 0 or step_s <= 0 or breathing_window_s <= 0:
        raise ValueError("windows and step must be positive")
    if len(frames) < 2:
        return []
    timestamps = np.asarray([frame.timestamp for frame in frames], dtype=np.float64)
    series = np.mean(np.stack([frame.amplitudes for frame in frames]), axis=1)
    step = float(np.median(np.diff(timestamps)))
    if step <= 0:
        raise ValueError("timestamps must increase")
    sample_rate = 1.0 / step
    features: list[WindowFeatures] = []
    start = timestamps[0]
    end = timestamps[-1]
    cursor = start + window_s
    while cursor <= end + 1e-9:
        features.append(
            _window_features(
                timestamps,
                series,
                sample_rate,
                cursor,
                window_s,
                breathing_window_s,
            )
        )
        cursor += step_s
    return features


def _window_features(
    timestamps: np.ndarray,
    series: np.ndarray,
    sample_rate: float,
    cursor: float,
    window_s: float,
    breathing_window_s: float,
) -> WindowFeatures:
    motion = _slice(timestamps, series, cursor - window_s, cursor)
    breathing = _slice(timestamps, series, cursor - breathing_window_s, cursor)
    return WindowFeatures(
        timestamp=float(cursor),
        variance=float(np.var(motion)),
        mean_abs_diff=_mean_abs_diff(motion),
        motion_energy=_band_energy(motion, sample_rate, *MOTION_BAND),
        breathing_energy=_band_energy(breathing, sample_rate, *BREATHING_BAND),
    )


def _slice(timestamps: np.ndarray, series: np.ndarray, start: float, end: float) -> np.ndarray:
    mask = (timestamps >= start - 1e-12) & (timestamps <= end + 1e-12)
    selected = series[mask]
    if selected.size == 0:
        return series[:1]
    return selected


def _mean_abs_diff(series: np.ndarray) -> float:
    if series.size < 2:
        return 0.0
    return float(np.mean(np.abs(np.diff(series))))


def _band_energy(series: np.ndarray, sample_rate: float, low_hz: float, high_hz: float) -> float:
    if series.size < 4:
        return 0.0
    centered = series - np.mean(series)
    taper = np.hanning(centered.size)
    spectrum = np.fft.rfft(centered * taper)
    freqs = np.fft.rfftfreq(centered.size, d=1.0 / sample_rate)
    # Divide by window energy so a longer breathing window is not rewarded for its length.
    power = np.square(np.abs(spectrum)) / max(float(np.sum(np.square(taper))), 1e-12)
    selected = (freqs >= low_hz) & (freqs < high_hz)
    if not np.any(selected):
        return 0.0
    return float(np.sum(power[selected]))
