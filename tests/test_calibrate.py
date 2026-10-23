from wifi_sonar.detect.calibrate import calibrate, load_calibration, save_calibration
from wifi_sonar.sources.simulated import SimulatedSource


def test_calibrate_empty_room_and_roundtrip(tmp_path) -> None:
    source = SimulatedSource(seed=9, duration_s=12.0, n_subcarriers=8)
    calibration = calibrate(source, seconds=12.0, k=6.0)
    for name in ("variance", "mean_abs_diff", "motion_energy", "breathing_energy"):
        assert calibration.thresholds[name] >= calibration.mean[name]
        assert calibration.std[name] >= 0.0
    path = tmp_path / "empty.json"
    save_calibration(path, calibration)
    loaded = load_calibration(path)
    assert loaded.k == 6.0
    assert loaded.seconds == 12.0
    assert loaded.thresholds == calibration.thresholds


def test_same_seed_calibrates_identically() -> None:
    first = calibrate(SimulatedSource(seed=2, duration_s=10.0, n_subcarriers=8), 10.0)
    second = calibrate(SimulatedSource(seed=2, duration_s=10.0, n_subcarriers=8), 10.0)
    assert first.mean == second.mean
    assert first.thresholds == second.thresholds
