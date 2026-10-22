import numpy as np
import pytest

from wifi_sonar.models import CSIFrame
from wifi_sonar.pipeline.features import FeatureConfig, extract_features


def _signal(values_at, n_subcarriers=4, fs=100.0, node_id="t"):
    frames = []
    for index, value in enumerate(values_at):
        frames.append(
            CSIFrame(
                timestamp=index / fs,
                rssi=-40.0,
                amplitudes=tuple(float(value) for _ in range(n_subcarriers)),
                phases=None,
                node_id=node_id,
            )
        )
    return frames


def _tone(freq_hz, amplitude, seconds=12.0, fs=100.0):
    times = np.arange(int(round(seconds * fs))) / fs
    return _signal(amplitude * np.sin(2 * np.pi * freq_hz * times), fs=fs)


def test_constant_signal_has_no_energy():
    frames = _signal(np.ones(1200))
    features = extract_features(frames, 100.0)
    assert features
    last = features[-1]
    assert last.variance == pytest.approx(0.0, abs=1e-9)
    assert last.mad == pytest.approx(0.0, abs=1e-9)
    assert last.motion_energy == pytest.approx(0.0, abs=1e-9)
    assert last.breath_energy == pytest.approx(0.0, abs=1e-9)
    assert features[1].timestamp - features[0].timestamp == pytest.approx(0.5)


def test_motion_and_breath_bands_separate_known_tones():
    walk = extract_features(_tone(2.0, 1.0), 100.0)[-1]
    breath = extract_features(_tone(0.25, 1.0), 100.0)[-1]

    assert walk.variance == pytest.approx(0.5, rel=0.05)
    assert walk.mad > 0
    assert walk.motion_energy > walk.breath_energy * 20

    assert breath.breath_energy > breath.motion_energy * 10
    assert breath.motion_energy < walk.motion_energy / 20


def test_optional_pca_keeps_a_shared_tone():
    config = FeatureConfig(pca_components=1)
    features = extract_features(_tone(2.0, 1.0), 100.0, config)
    last = features[-1]
    plain = extract_features(_tone(2.0, 1.0), 100.0)[-1]
    assert np.isfinite(last.motion_energy)
    assert last.motion_energy > plain.motion_energy * 0.5
    assert last.breath_energy < last.motion_energy / 10
