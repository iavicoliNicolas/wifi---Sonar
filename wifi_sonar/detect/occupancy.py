"""Conteo anónimo de personas en alcance.

El resultado es 0, 1 o 2+. No hay nombre, trayectoria ni identidad: dos picos
en la misma ventana no dicen quién es quién, solo que hay más de una firma.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

import numpy as np

from wifi_sonar.models import CSIFrame

_WINDOW_S = 12.0
_MIN_WINDOW_S = 8.0
_BREATH_BAND = (0.12, 0.55)
_MOTION_BAND = (0.8, 4.5)
_FLOOR_BAND = (6.0, 12.0)
_PEAK_RATIO = 40.0
_PROMINENCE = 1.8
_RSSI_CONFIDENCE = 0.25


@dataclass(frozen=True, slots=True)
class OccupancyEstimate:
    """Cuántas firmas se distinguen, no quiénes son."""

    count: int
    label: str
    confidence: float
    low_confidence: bool

    def __post_init__(self) -> None:
        if self.count not in (0, 1, 2):
            raise ValueError("count must be 0, 1 or 2")
        if self.label not in ("0", "1", "2+"):
            raise ValueError("label must be 0, 1 or 2+")
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError("confidence must be between 0 and 1")

    def as_dict(self) -> dict[str, object]:
        return {
            "count": self.count,
            "label": self.label,
            "confidence": self.confidence,
            "low_confidence": self.low_confidence,
        }


def estimate_occupancy(
    frames: Sequence[CSIFrame],
    sample_rate_hz: float,
    *,
    mode: str = "csi",
) -> OccupancyEstimate:
    """Cuenta picos de respiración o caminata en la última ventana.

    Un solo seno claro es 1. Dos picos separados son 2+. En modo RSSI, o con
    una sola subportadora, la confianza queda baja: esa señal no separa personas.
    """

    if sample_rate_hz <= 0:
        raise ValueError("sample_rate_hz must be positive")
    if mode not in ("csi", "rssi"):
        raise ValueError("mode must be csi or rssi")
    needed = int(_MIN_WINDOW_S * sample_rate_hz)
    if len(frames) < needed:
        return _estimate(0, 0.2, low=True, mode=mode)
    window = frames[-int(_WINDOW_S * sample_rate_hz) :]
    series, used = _mean_series(window)
    if series is None:
        return _estimate(0, 0.2, low=True, mode=mode)
    freqs, power = _periodogram(series, sample_rate_hz)
    floor = _noise_floor(freqs, power)
    peaks = _peaks(freqs, power, floor, _BREATH_BAND) + _peaks(freqs, power, floor, _MOTION_BAND)
    count = min(2, len(peaks))
    if count == 0:
        confidence = 0.85
    elif count == 1:
        confidence = 0.75
    else:
        confidence = 0.65
    low = mode == "rssi" or used < 2
    return _estimate(count, confidence, low=low, mode=mode)


def _estimate(count: int, confidence: float, *, low: bool, mode: str) -> OccupancyEstimate:
    if mode == "rssi" or low:
        confidence = min(confidence, _RSSI_CONFIDENCE)
        low = True
    label = "2+" if count >= 2 else str(count)
    return OccupancyEstimate(
        count=count,
        label=label,
        confidence=confidence,
        low_confidence=low,
    )


def _mean_series(frames: Sequence[CSIFrame]) -> tuple[np.ndarray | None, int]:
    width = len(frames[0].amplitudes)
    if any(len(frame.amplitudes) != width for frame in frames):
        return None, 0
    matrix = np.asarray([frame.amplitudes for frame in frames], dtype=float)
    energy = np.mean(np.abs(matrix), axis=0)
    keep = energy > 1e-3
    used = int(np.count_nonzero(keep))
    if used == 0:
        return None, 0
    return matrix[:, keep].mean(axis=1), used


def _periodogram(series: np.ndarray, sample_rate_hz: float) -> tuple[np.ndarray, np.ndarray]:
    centered = series - float(np.mean(series))
    window = np.hanning(len(centered))
    spectrum = np.fft.rfft(centered * window)
    power = (np.abs(spectrum) ** 2) / np.sum(window**2)
    freqs = np.fft.rfftfreq(len(centered), d=1.0 / sample_rate_hz)
    return freqs, power


def _noise_floor(freqs: np.ndarray, power: np.ndarray) -> float:
    mask = (freqs >= _FLOOR_BAND[0]) & (freqs < _FLOOR_BAND[1])
    if not np.any(mask):
        return float(np.median(power))
    return float(max(np.median(power[mask]), 1e-12))


def _peaks(
    freqs: np.ndarray,
    power: np.ndarray,
    floor: float,
    band: tuple[float, float],
) -> list[float]:
    low, high = band
    idx = np.flatnonzero((freqs >= low - 0.15) & (freqs < high + 0.15))
    found: list[tuple[float, float]] = []
    for pos in range(1, len(idx) - 1):
        freq = float(freqs[idx[pos]])
        if not low <= freq < high:
            continue
        level = float(power[idx[pos]])
        left = float(power[idx[pos - 1]])
        right = float(power[idx[pos + 1]])
        if level < left or level <= right:
            continue
        if level < floor * _PEAK_RATIO or level < _PROMINENCE * max(left, right):
            continue
        found.append((freq, level))
    return _merge_close(found)


def _merge_close(peaks: list[tuple[float, float]]) -> list[float]:
    ordered = sorted(peaks, key=lambda item: item[0])
    kept: list[tuple[float, float]] = []
    for freq, level in ordered:
        if kept and freq - kept[-1][0] < 0.12:
            if level > kept[-1][1]:
                kept[-1] = (freq, level)
            continue
        kept.append((freq, level))
    return [freq for freq, _level in kept]
