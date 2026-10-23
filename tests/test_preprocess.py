import numpy as np
from wifi_sonar.pipeline.preprocess import preprocess
from wifi_sonar.sources.frame import CSIFrame
from wifi_sonar.sources.simulated import SimulatedSource


def _frames_from_matrix(amplitudes: np.ndarray, *, step: float = 0.02) -> list[CSIFrame]:
    frames = []
    for index, row in enumerate(amplitudes):
        frames.append(
            CSIFrame(
                timestamp=index * step,
                rssi=-40.0,
                amplitudes=row,
                phases=np.zeros_like(row),
                node_id="n0",
            )
        )
    return frames


def test_hampel_removes_a_spike_and_keeps_the_trace_stable() -> None:
    rng = np.random.default_rng(0)
    amplitudes = 1.0 + 0.01 * rng.normal(size=(40, 4))
    amplitudes[20, 1] = 1_000.0
    cleaned = preprocess(_frames_from_matrix(amplitudes))
    matrix = np.stack([frame.amplitudes for frame in cleaned])
    raw_var = float(np.var(amplitudes[:, 1]))
    clean_var = float(np.var(matrix[:, 1]))
    assert np.max(np.abs(matrix)) < 5
    assert clean_var < raw_var / 100


def test_missing_sample_is_interpolated() -> None:
    amplitudes = np.ones((10, 2))
    amplitudes[:, 0] = np.linspace(0.0, 9.0, 10)
    amplitudes[5, 0] = np.nan
    frames = _frames_from_matrix(amplitudes)
    frames[5] = CSIFrame(
        timestamp=frames[5].timestamp,
        rssi=frames[5].rssi,
        amplitudes=amplitudes[5],
        phases=frames[5].phases,
        node_id="n0",
    )
    cleaned = preprocess(frames)
    series = np.stack([frame.amplitudes for frame in cleaned])[:, 0]
    assert np.isfinite(series).all()
    # After per-subcarrier normalization the filled point still sits between neighbors.
    assert series[4] < series[5] < series[6]


def test_timestamp_gap_inserts_a_frame() -> None:
    amplitudes = np.column_stack([np.linspace(0.0, 1.0, 12), np.ones(12)])
    frames = _frames_from_matrix(amplitudes, step=0.02)
    # Keep the regular cadence, then jump across several dropped packets.
    kept = frames[:4] + frames[10:]
    cleaned = preprocess(kept)
    timestamps = [frame.timestamp for frame in cleaned]
    assert len(cleaned) > len(kept)
    hole_start = frames[3].timestamp
    hole_end = frames[10].timestamp
    assert any(hole_start < stamp < hole_end for stamp in timestamps)


def test_null_subcarrier_is_removed_and_scales_match() -> None:
    rng = np.random.default_rng(1)
    quiet = 1.0 + 0.01 * rng.normal(size=(30, 1))
    loud = 10.0 + 0.1 * rng.normal(size=(30, 1))
    dead = np.zeros((30, 1))
    amplitudes = np.hstack([quiet, loud, dead])
    cleaned = preprocess(_frames_from_matrix(amplitudes))
    assert cleaned[0].n_subcarriers == 2
    matrix = np.stack([frame.amplitudes for frame in cleaned])
    scales = np.median(np.abs(matrix), axis=0)
    assert scales.max() / scales.min() < 1.5


def test_simulator_trace_stays_finite() -> None:
    source = SimulatedSource(seed=2, duration_s=1.0, n_subcarriers=8)
    cleaned = preprocess(source.frames())
    matrix = np.stack([frame.amplitudes for frame in cleaned])
    assert np.isfinite(matrix).all()
    assert cleaned[0].n_subcarriers == 8
