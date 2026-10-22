import pytest

from wifi_sonar.detect.calibrate import calibrate, load_calibration
from wifi_sonar.sources.simulated import SimConfig, SimulatedSource


def test_calibrate_persists_thresholds_from_an_empty_room(tmp_path):
    source = SimulatedSource(SimConfig(seed=11, duration_s=22.0))
    destination = tmp_path / "baseline.json"
    calibration = calibrate(source, seconds=20.0, k=4.0, path=destination)

    assert destination.is_file()
    loaded = load_calibration(destination)
    assert loaded.created_at == calibration.created_at
    assert loaded.k == 4.0
    assert loaded.sample_rate_hz == pytest.approx(100.0)
    for name in ("variance", "mad", "motion_energy", "breath_energy"):
        assert loaded.mean[name] == pytest.approx(calibration.mean[name])
        assert loaded.std[name] == pytest.approx(calibration.std[name])
        assert loaded.thresholds[name] == pytest.approx(
            calibration.mean[name] + 4.0 * calibration.std[name]
        )
        assert loaded.thresholds[name] >= loaded.mean[name]
    assert loaded.mean["motion_energy"] > 0


def test_short_capture_is_rejected():
    source = SimulatedSource(SimConfig(seed=1, duration_s=5.0))
    with pytest.raises(ValueError):
        calibrate(source, seconds=5.0)
