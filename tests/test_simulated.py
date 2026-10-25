import numpy as np
from wifi_sonar.sources.simulated import ScenarioEvent, SimulatedSource, amplitude_variance


def test_frame_shape_and_version_fields() -> None:
    source = SimulatedSource(seed=7, duration_s=0.2, sample_rate_hz=50.0)
    frames = source.frames()
    assert len(frames) == 10
    frame = frames[0]
    assert frame.n_subcarriers == 52
    assert frame.phases is not None
    assert frame.phases.shape == (52,)
    assert frame.node_id == "sim-0"
    assert np.isfinite(frame.rssi)


def test_same_seed_is_deterministic() -> None:
    events = (ScenarioEvent("walk", 0.2, 0.4),)
    first = SimulatedSource(seed=3, duration_s=1.0, events=events).frames()
    second = SimulatedSource(seed=3, duration_s=1.0, events=events).frames()
    for left, right in zip(first, second, strict=True):
        assert left.timestamp == right.timestamp
        assert left.rssi == right.rssi
        assert np.array_equal(left.amplitudes, right.amplitudes)
        assert left.phases is not None and right.phases is not None
        assert np.array_equal(left.phases, right.phases)


def test_events_change_variance_in_the_expected_direction() -> None:
    empty = SimulatedSource(seed=11, duration_s=4.0)
    still = SimulatedSource(
        seed=11,
        duration_s=4.0,
        events=(ScenarioEvent("still", 0.0, 4.0),),
    )
    walk = SimulatedSource(
        seed=11,
        duration_s=4.0,
        events=(ScenarioEvent("walk", 0.0, 4.0),),
    )
    empty_var = amplitude_variance(empty.frames())
    still_var = amplitude_variance(still.frames())
    walk_var = amplitude_variance(walk.frames())
    assert still_var > empty_var * 2
    assert walk_var > still_var * 2


def test_walk_segment_is_noisier_than_the_surrounding_empty_room() -> None:
    source = SimulatedSource(
        seed=5,
        duration_s=6.0,
        events=(ScenarioEvent("enter", 2.0, 0.4), ScenarioEvent("walk", 2.4, 2.0)),
    )
    frames = source.frames()
    before = [frame for frame in frames if frame.timestamp < 2.0]
    during = [frame for frame in frames if 2.4 <= frame.timestamp < 4.4]
    assert amplitude_variance(during) > amplitude_variance(before) * 3
