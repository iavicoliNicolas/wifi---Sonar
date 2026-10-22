import numpy as np

from wifi_sonar.models import CSIFrame
from wifi_sonar.pipeline.preprocess import PreprocessConfig, preprocess


def _frames(samples, fs=100.0, node_id="n"):
    frames = []
    for index, amplitudes in enumerate(samples):
        frames.append(
            CSIFrame(
                timestamp=index / fs,
                rssi=-40.0,
                amplitudes=tuple(amplitudes),
                phases=None,
                node_id=node_id,
            )
        )
    return frames


def test_hampel_removes_a_spike_and_keeps_the_trace_finite():
    rng = np.random.default_rng(0)
    base = rng.normal(1.0, 0.01, size=(80, 3))
    base[40, 1] = 50.0
    cleaned = preprocess(
        _frames(base),
        100.0,
        PreprocessConfig(normalize=False, null_threshold=0.0),
    )
    matrix = np.array([frame.amplitudes for frame in cleaned])
    assert matrix[40, 1] < 2.0
    assert np.isfinite(matrix).all()
    assert float(matrix.var()) < 1.0


def test_missing_packet_is_interpolated():
    frames = [
        CSIFrame(0.0, -40.0, (0.0,), None, "n"),
        CSIFrame(0.01, -42.0, (2.0,), None, "n"),
        CSIFrame(0.03, -36.0, (6.0,), None, "n"),
    ]
    cleaned = preprocess(
        frames,
        100.0,
        PreprocessConfig(normalize=False, null_threshold=0.0, hampel_window=3),
    )
    by_time = {round(frame.timestamp, 5): frame for frame in cleaned}
    filled = by_time[0.02]
    assert np.isclose(filled.amplitudes[0], 4.0)
    assert np.isclose(filled.rssi, -39.0)


def test_null_subcarrier_is_removed_and_amplitude_is_normalized():
    samples = np.tile(np.array([0.0, 4.0, 8.0]), (30, 1))
    cleaned = preprocess(samples_to_frames(samples), 100.0)
    assert cleaned[0].n_subcarriers == 2
    medians = np.median(np.abs(np.array([frame.amplitudes for frame in cleaned])), axis=0)
    assert np.allclose(medians, 1.0)


def samples_to_frames(samples, fs=100.0):
    return _frames(samples, fs=fs)
