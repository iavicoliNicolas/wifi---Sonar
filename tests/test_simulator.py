import numpy as np
import pytest

from wifi_sonar.sources.simulated import SimConfig, SimEvent, SimulatedSource, demo_cycle


def _variance(frames, drop_null: bool = True) -> float:
    matrix = np.array([frame.amplitudes for frame in frames], dtype=float)
    if drop_null and matrix.shape[1] > 1:
        matrix = matrix[:, 1:]
    # Varianza temporal media: el patrón estático entre subportadoras no cuenta.
    return float(matrix.var(axis=0).mean())


def test_generate_is_deterministic_and_shaped():
    config = SimConfig(seed=7, duration_s=2.0)
    first = SimulatedSource(config).generate()
    second = SimulatedSource(config).generate()
    other = SimulatedSource(SimConfig(seed=8, duration_s=2.0)).generate()

    assert first == second
    assert first != other
    assert len(first) == 200
    assert first[0].n_subcarriers == 52
    assert first[0].amplitudes[0] == 0.0
    assert first[0].phases is not None
    assert len(first[0].phases) == 52
    assert first[-1].timestamp == pytest.approx(1.99)


def test_events_change_variance_in_the_expected_order():
    duration = 20.0
    config = SimConfig(
        seed=3,
        duration_s=duration,
        events=(
            SimEvent("enter", 2.0, 1.0),
            SimEvent("walk", 6.0, 4.0),
            SimEvent("still", 12.0, 4.0),
            SimEvent("leave", 17.0, 1.0),
        ),
    )
    frames = SimulatedSource(config).generate()
    fs = 100

    def slice_var(start_s: float, length_s: float) -> float:
        start = int(start_s * fs)
        stop = int((start_s + length_s) * fs)
        return _variance(frames[start:stop])

    empty = slice_var(0.0, 1.5)
    burst = slice_var(2.1, 0.8)
    walk = slice_var(7.0, 2.5)
    still = slice_var(13.0, 2.5)

    assert walk > empty * 10
    assert still > empty * 2
    assert still < walk / 5
    assert burst > empty * 5


def test_unknown_event_is_rejected():
    with pytest.raises(ValueError):
        SimEvent("sleep", 0.0, 1.0)


def test_demo_cycle_fits_the_period():
    events = demo_cycle()
    assert {event.kind for event in events} == {"enter", "walk", "still", "leave"}
    assert max(event.start_s + event.duration_s for event in events) <= 40.0
