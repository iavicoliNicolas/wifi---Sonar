"""Clean a CSI trace before features are computed.

Steps, in order: fill missing samples, interpolate timestamp gaps, reject
outliers with a Hampel filter, drop dead subcarriers, then scale each
remaining subcarrier by its median absolute amplitude.
"""

from collections.abc import Sequence

import numpy as np

from wifi_sonar.sources.frame import CSIFrame


def preprocess(
    frames: Sequence[CSIFrame],
    *,
    hampel_window: int = 7,
    hampel_sigma: float = 3.0,
    null_fraction: float = 0.05,
    gap_factor: float = 1.5,
) -> list[CSIFrame]:
    if not frames:
        return []
    if hampel_window < 3 or hampel_window % 2 == 0:
        raise ValueError("hampel_window must be an odd integer >= 3")
    node_ids = [frame.node_id for frame in frames]
    timestamps = np.asarray([frame.timestamp for frame in frames], dtype=np.float64)
    rssi = np.asarray([frame.rssi for frame in frames], dtype=np.float64)
    amplitudes = np.stack([frame.amplitudes for frame in frames])
    phases = _stack_phases(frames, amplitudes.shape)

    amplitudes = _fill_nans(amplitudes)
    phases = _fill_nans(phases)
    timestamps, rssi, amplitudes, phases, node_ids = _interpolate_gaps(
        timestamps, rssi, amplitudes, phases, node_ids, gap_factor=gap_factor
    )
    amplitudes = _hampel_matrix(amplitudes, hampel_window, hampel_sigma)
    keep = _live_subcarriers(amplitudes, null_fraction)
    amplitudes = _normalize(amplitudes[:, keep])
    phases = phases[:, keep]

    cleaned: list[CSIFrame] = []
    for index in range(amplitudes.shape[0]):
        cleaned.append(
            CSIFrame(
                timestamp=float(timestamps[index]),
                rssi=float(rssi[index]),
                amplitudes=amplitudes[index],
                phases=phases[index],
                node_id=node_ids[index],
            )
        )
    return cleaned


def _stack_phases(frames: Sequence[CSIFrame], shape: tuple[int, int]) -> np.ndarray:
    phases = np.zeros(shape, dtype=np.float64)
    for index, frame in enumerate(frames):
        if frame.phases is None:
            phases[index] = np.nan
        else:
            phases[index] = frame.phases
    return phases


def _fill_nans(values: np.ndarray) -> np.ndarray:
    filled = values.copy()
    positions = np.arange(values.shape[0])
    for column in range(values.shape[1]):
        series = filled[:, column]
        good = np.isfinite(series)
        if good.all():
            continue
        if not good.any():
            filled[:, column] = 0.0
            continue
        filled[:, column] = np.interp(positions, positions[good], series[good])
    return filled


def _interpolate_gaps(
    timestamps: np.ndarray,
    rssi: np.ndarray,
    amplitudes: np.ndarray,
    phases: np.ndarray,
    node_ids: list[str],
    *,
    gap_factor: float,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, list[str]]:
    if len(timestamps) < 2:
        return timestamps, rssi, amplitudes, phases, node_ids
    deltas = np.diff(timestamps)
    positive = deltas[deltas > 0]
    step = float(np.median(positive)) if positive.size else 0.0
    if step <= 0:
        return timestamps, rssi, amplitudes, phases, node_ids

    times: list[float] = []
    powers: list[float] = []
    amp_rows: list[np.ndarray] = []
    phase_rows: list[np.ndarray] = []
    nodes: list[str] = []
    for index in range(len(timestamps)):
        if index > 0:
            gap = float(timestamps[index] - timestamps[index - 1])
            missing = int(round(gap / step)) - 1
            if gap > gap_factor * step and missing > 0:
                for step_index in range(1, missing + 1):
                    weight = step_index / (missing + 1)
                    times.append(float(timestamps[index - 1] + weight * gap))
                    powers.append(float(rssi[index - 1] + weight * (rssi[index] - rssi[index - 1])))
                    amp_rows.append(
                        amplitudes[index - 1] + weight * (amplitudes[index] - amplitudes[index - 1])
                    )
                    phase_rows.append(
                        phases[index - 1] + weight * (phases[index] - phases[index - 1])
                    )
                    nodes.append(node_ids[index - 1])
        times.append(float(timestamps[index]))
        powers.append(float(rssi[index]))
        amp_rows.append(amplitudes[index])
        phase_rows.append(phases[index])
        nodes.append(node_ids[index])
    return (
        np.asarray(times),
        np.asarray(powers),
        np.stack(amp_rows),
        np.stack(phase_rows),
        nodes,
    )


def _hampel_matrix(values: np.ndarray, window: int, n_sigma: float) -> np.ndarray:
    cleaned = np.empty_like(values)
    for column in range(values.shape[1]):
        cleaned[:, column] = _hampel(values[:, column], window, n_sigma)
    return cleaned


def _hampel(series: np.ndarray, window: int, n_sigma: float) -> np.ndarray:
    cleaned = series.copy()
    half = window // 2
    for index in range(len(series)):
        lo = max(0, index - half)
        hi = min(len(series), index + half + 1)
        segment = series[lo:hi]
        median = float(np.median(segment))
        mad = float(np.median(np.abs(segment - median)))
        scale = 1.4826 * mad
        if scale == 0.0:
            if series[index] != median:
                cleaned[index] = median
            continue
        if abs(series[index] - median) > n_sigma * scale:
            cleaned[index] = median
    return cleaned


def _live_subcarriers(amplitudes: np.ndarray, null_fraction: float) -> np.ndarray:
    scales = np.median(np.abs(amplitudes), axis=0)
    reference = float(np.median(scales))
    if reference <= 0.0:
        return scales > 0.0
    return scales >= null_fraction * reference


def _normalize(amplitudes: np.ndarray) -> np.ndarray:
    scales = np.median(np.abs(amplitudes), axis=0)
    scales = np.maximum(scales, 1e-9)
    return amplitudes / scales
