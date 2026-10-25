import numpy as np
from wifi_sonar.pipeline.features import extract_features
from wifi_sonar.sources.frame import CSIFrame
from wifi_sonar.sources.simulated import ScenarioEvent, SimulatedSource


def _tone(freq_hz: float, seconds: float, *, amplitude: float = 1.0, sample_rate: float = 50.0):
    count = int(round(seconds * sample_rate)) + 1
    times = np.linspace(0.0, seconds, count)
    wave = amplitude * np.sin(2.0 * np.pi * freq_hz * times)
    frames = []
    for timestamp, sample in zip(times, wave, strict=True):
        frames.append(
            CSIFrame(
                timestamp=float(timestamp),
                rssi=-40.0,
                amplitudes=np.array([sample + 1.0, sample + 1.0]),
                phases=None,
                node_id="tone",
            )
        )
    return frames


def test_window_count_and_constant_signal() -> None:
    frames = _tone(0.0, 4.0, amplitude=0.0)
    features = extract_features(frames, window_s=2.0, step_s=0.5)
    assert len(features) == 5
    assert features[0].timestamp == 2.0
    assert features[-1].timestamp == 4.0
    assert features[0].variance == 0.0
    assert features[0].mean_abs_diff == 0.0
    assert features[0].motion_energy == 0.0
    assert features[0].breathing_energy == 0.0


def test_motion_tone_beats_breathing_tone() -> None:
    walking = extract_features(_tone(2.0, 4.0))
    breathing = extract_features(_tone(0.25, 12.0))
    walk_motion = max(item.motion_energy for item in walking)
    walk_breath = max(item.breathing_energy for item in walking)
    still_motion = max(item.motion_energy for item in breathing)
    still_breath = max(item.breathing_energy for item in breathing)
    assert walk_motion > 0.1
    assert walk_motion > walk_breath * 5
    assert still_breath > still_motion * 2
    assert still_breath > walk_breath


def test_known_variance() -> None:
    times = np.linspace(0.0, 2.0, 100)
    values = np.array([0.0, 1.0] * 50)
    frames = [
        CSIFrame(
            timestamp=float(t),
            rssi=-40.0,
            amplitudes=np.array([value]),
            phases=None,
            node_id="n",
        )
        for t, value in zip(times, values, strict=True)
    ]
    features = extract_features(frames, window_s=2.0, step_s=2.0)
    assert features[0].variance == 0.25


def test_simulator_walk_raises_motion_energy() -> None:
    empty = extract_features(SimulatedSource(seed=1, duration_s=4.0).frames())
    walk = extract_features(
        SimulatedSource(
            seed=1,
            duration_s=4.0,
            events=(ScenarioEvent("walk", 0.0, 4.0),),
        ).frames()
    )
    assert max(item.motion_energy for item in walk) > max(item.motion_energy for item in empty) * 5
