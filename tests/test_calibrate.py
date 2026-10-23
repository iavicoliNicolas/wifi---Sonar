from wifi_sonar.detect.calibrate import (
    Calibration,
    calibrate,
    load_calibration,
    quality_report,
    save_calibration,
)
from wifi_sonar.runtime import SonarConfig, SonarState
from wifi_sonar.sources.simulated import ScenarioEvent, SimulatedSource


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


def test_quality_report_labels_the_capture() -> None:
    empty = calibrate(SimulatedSource(seed=1, duration_s=12.0, n_subcarriers=8), 12.0)
    assert quality_report(empty)["label"] == "buena"
    short = Calibration(
        mean=empty.mean,
        std=empty.std,
        thresholds=empty.thresholds,
        k=empty.k,
        seconds=4.0,
    )
    assert quality_report(short)["label"] == "corta"
    disturbed = calibrate(
        SimulatedSource(
            seed=1,
            duration_s=12.0,
            n_subcarriers=8,
            events=(ScenarioEvent("walk", 6.0, 6.0),),
        ),
        12.0,
    )
    assert quality_report(disturbed)["label"] == "inestable"
    loud = calibrate(
        SimulatedSource(
            seed=1,
            duration_s=12.0,
            n_subcarriers=8,
            events=(ScenarioEvent("walk", 0.0, 12.0),),
        ),
        12.0,
    )
    assert quality_report(loud)["label"] == "alta"


def test_an_attached_source_replaces_the_empty_simulator() -> None:
    config = SonarConfig(n_subcarriers=8)
    state = SonarState(config=config)
    attached = state.calibrate(
        12.0,
        source=SimulatedSource(seed=4, duration_s=12.0, n_subcarriers=8),
    )
    untouched = SonarState(config=config).calibrate(12.0)
    reference = calibrate(SimulatedSource(seed=1, duration_s=12.0, n_subcarriers=8), 12.0)
    assert untouched.mean == reference.mean
    assert attached.mean["motion_energy"] != reference.mean["motion_energy"]
    assert quality_report(attached)["label"] == "buena"


def test_recent_walk_is_not_a_good_baseline() -> None:
    state = SonarState(config=SonarConfig(n_subcarriers=8))
    state.capture_from_recent = True
    source = SimulatedSource(
        seed=1,
        duration_s=12.0,
        n_subcarriers=8,
        events=(ScenarioEvent("walk", 0.0, 12.0),),
    )
    for frame in source.frames():
        state.remember(frame)
    assert quality_report(state.calibrate(12.0))["label"] != "buena"
    state.recent.clear()
    fallback = state.calibrate(12.0)
    reference = calibrate(SimulatedSource(seed=1, duration_s=12.0, n_subcarriers=8), 12.0)
    assert fallback.mean == reference.mean


def test_same_seed_calibrates_identically() -> None:
    first = calibrate(SimulatedSource(seed=2, duration_s=10.0, n_subcarriers=8), 10.0)
    second = calibrate(SimulatedSource(seed=2, duration_s=10.0, n_subcarriers=8), 10.0)
    assert first.mean == second.mean
    assert first.thresholds == second.thresholds
