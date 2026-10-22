"""Hampel, interpolación de huecos, subportadoras nulas y normalización."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

import numpy as np
from numpy.lib.stride_tricks import sliding_window_view

from wifi_sonar.models import CSIFrame


@dataclass(frozen=True, slots=True)
class PreprocessConfig:
    hampel_window: int = 7
    hampel_n_sigmas: float = 3.0
    null_threshold: float = 1e-3
    normalize: bool = True


def preprocess(
    frames: Sequence[CSIFrame],
    sample_rate_hz: float,
    config: PreprocessConfig | None = None,
) -> list[CSIFrame]:
    """Devuelve frames uniformes, sin outliers groseros ni subportadoras muertas.

    La normalización divide cada subportadora por su mediana de amplitud para
    sacar el desvanecimiento estático. Es por lote: el llamador decide la ventana.
    """

    if sample_rate_hz <= 0:
        raise ValueError("sample_rate_hz must be positive")
    if not frames:
        return []
    cfg = config if config is not None else PreprocessConfig()
    width = frames[0].n_subcarriers
    if any(frame.n_subcarriers != width for frame in frames):
        raise ValueError("all frames must share the subcarrier count")

    times = np.array([frame.timestamp for frame in frames], dtype=float)
    amplitudes = np.array([frame.amplitudes for frame in frames], dtype=float)
    rssi = np.array([frame.rssi for frame in frames], dtype=float)
    has_phases = all(frame.phases is not None for frame in frames)
    phases = np.array([frame.phases for frame in frames], dtype=float) if has_phases else None

    grid, amplitudes, rssi, phases, node_ids = _resample(
        frames, times, amplitudes, rssi, phases, sample_rate_hz
    )
    amplitudes = _hampel(amplitudes, cfg.hampel_window, cfg.hampel_n_sigmas)
    keep = np.max(np.abs(amplitudes), axis=0) >= cfg.null_threshold
    if not np.any(keep):
        raise ValueError("every subcarrier was classified as null")
    amplitudes = amplitudes[:, keep]
    if phases is not None:
        phases = phases[:, keep]
    if cfg.normalize:
        scale = np.median(np.abs(amplitudes), axis=0)
        scale = np.where(scale < 1e-12, 1.0, scale)
        amplitudes = amplitudes / scale

    cleaned: list[CSIFrame] = []
    for index in range(len(grid)):
        phase_row = None if phases is None else tuple(float(value) for value in phases[index])
        cleaned.append(
            CSIFrame(
                timestamp=float(grid[index]),
                rssi=float(rssi[index]),
                amplitudes=tuple(float(value) for value in amplitudes[index]),
                phases=phase_row,
                node_id=node_ids[index],
            )
        )
    return cleaned


def _resample(frames, times, amplitudes, rssi, phases, sample_rate_hz):
    order = np.argsort(times)
    times = times[order]
    amplitudes = amplitudes[order]
    rssi = rssi[order]
    if phases is not None:
        phases = phases[order]
    ordered = [frames[int(i)] for i in order]
    # np.interp needs strictly increasing sample times.
    unique_times, unique_index = np.unique(times, return_index=True)
    times = unique_times
    amplitudes = amplitudes[unique_index]
    rssi = rssi[unique_index]
    if phases is not None:
        phases = phases[unique_index]
    ordered = [ordered[int(i)] for i in unique_index]

    if len(times) == 1:
        return times, amplitudes, rssi, phases, [ordered[0].node_id]

    dt = 1.0 / sample_rate_hz
    count = int(round((times[-1] - times[0]) / dt)) + 1
    grid = times[0] + np.arange(count) * dt
    grid[-1] = times[-1]
    filled = np.column_stack(
        [np.interp(grid, times, amplitudes[:, column]) for column in range(amplitudes.shape[1])]
    )
    filled_rssi = np.interp(grid, times, rssi)
    filled_phases = None
    if phases is not None:
        filled_phases = np.column_stack(
            [np.interp(grid, times, phases[:, column]) for column in range(phases.shape[1])]
        )
    nearest = np.abs(grid[:, None] - times[None, :]).argmin(axis=1)
    node_ids = [ordered[int(index)].node_id for index in nearest]
    return grid, filled, filled_rssi, filled_phases, node_ids


def _hampel(matrix: np.ndarray, window: int, n_sigmas: float) -> np.ndarray:
    if window < 3 or matrix.shape[0] < window:
        return matrix
    if window % 2 == 0:
        window += 1
    half = window // 2
    padded = np.pad(matrix, ((half, half), (0, 0)), mode="edge")
    windows = sliding_window_view(padded, window_shape=window, axis=0)
    median = np.median(windows, axis=-1)
    mad = np.median(np.abs(windows - median[..., None]), axis=-1)
    sigma = 1.4826 * mad
    outlier = (sigma > 0) & (np.abs(matrix - median) > n_sigmas * sigma)
    cleaned = matrix.copy()
    cleaned[outlier] = median[outlier]
    return cleaned
