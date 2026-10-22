"""Features de una ventana deslizante sobre CSI ya preprocesado."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

import numpy as np

from wifi_sonar.models import CSIFrame

FEATURE_NAMES = ("variance", "mad", "motion_energy", "breath_energy")


@dataclass(frozen=True, slots=True)
class FeatureConfig:
    window_s: float = 2.0
    step_s: float = 0.5
    # La banda de respiración no se resuelve en 2 s. El espectro usa una ventana más larga.
    spectrum_window_s: float = 10.0
    motion_band: tuple[float, float] = (0.5, 5.0)
    breath_band: tuple[float, float] = (0.1, 0.5)
    pca_components: int | None = None


@dataclass(frozen=True, slots=True)
class WindowFeatures:
    timestamp: float
    variance: float
    mad: float
    motion_energy: float
    breath_energy: float

    def as_dict(self) -> dict[str, float]:
        return {name: float(getattr(self, name)) for name in FEATURE_NAMES}


def extract_features(
    frames: Sequence[CSIFrame],
    sample_rate_hz: float,
    config: FeatureConfig | None = None,
) -> list[WindowFeatures]:
    if sample_rate_hz <= 0:
        raise ValueError("sample_rate_hz must be positive")
    if len(frames) < 2:
        return []
    cfg = config if config is not None else FeatureConfig()
    amplitudes = np.array([frame.amplitudes for frame in frames], dtype=float)
    times = np.array([frame.timestamp for frame in frames], dtype=float)
    short = max(4, int(round(cfg.window_s * sample_rate_hz)))
    step = max(1, int(round(cfg.step_s * sample_rate_hz)))
    spectrum = max(short, int(round(cfg.spectrum_window_s * sample_rate_hz)))

    features: list[WindowFeatures] = []
    end = spectrum
    while end <= len(amplitudes):
        short_view = _maybe_pca(amplitudes[end - short : end], cfg.pca_components)
        spectrum_view = _maybe_pca(amplitudes[end - spectrum : end], cfg.pca_components)
        features.append(
            WindowFeatures(
                timestamp=float(times[end - 1]),
                variance=float(short_view.var(axis=0).mean()),
                mad=_mean_abs_diff(short_view),
                motion_energy=_band_energy(
                    spectrum_view, sample_rate_hz, cfg.motion_band[0], cfg.motion_band[1]
                ),
                breath_energy=_band_energy(
                    spectrum_view, sample_rate_hz, cfg.breath_band[0], cfg.breath_band[1]
                ),
            )
        )
        end += step
    return features


def _mean_abs_diff(matrix: np.ndarray) -> float:
    if matrix.shape[0] < 2:
        return 0.0
    return float(np.abs(np.diff(matrix, axis=0)).mean())


def _maybe_pca(matrix: np.ndarray, components: int | None) -> np.ndarray:
    if components is None or matrix.shape[1] <= 1:
        return matrix
    centered = matrix - matrix.mean(axis=0, keepdims=True)
    _, singular, vh = np.linalg.svd(centered, full_matrices=False)
    rank = max(1, min(components, singular.shape[0], vh.shape[0]))
    return centered @ vh[:rank].T


def _band_energy(matrix: np.ndarray, sample_rate_hz: float, low_hz: float, high_hz: float) -> float:
    """Energía de banda con el periodograma de Welch de un segmento y ventana de Hann.

    Un solo segmento conserva la resolución: partir 10 s en mitades no separa 0.25 Hz de 0.5 Hz.
    """

    if matrix.shape[0] < 4:
        return 0.0
    freqs, power = _hann_periodogram(matrix, sample_rate_hz)
    mask = (freqs >= low_hz) & (freqs < high_hz)
    if not np.any(mask):
        return 0.0
    return float(power[mask].sum(axis=0).mean())


def _hann_periodogram(matrix: np.ndarray, sample_rate_hz: float) -> tuple[np.ndarray, np.ndarray]:
    length = matrix.shape[0]
    window = np.hanning(length)
    centered = matrix - matrix.mean(axis=0, keepdims=True)
    tapered = centered * window[:, None]
    spectrum = np.fft.rfft(tapered, axis=0)
    power = (np.abs(spectrum) ** 2) / np.sum(window**2)
    freqs = np.fft.rfftfreq(length, d=1.0 / sample_rate_hz)
    return freqs, power
