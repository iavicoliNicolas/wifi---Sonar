from wifi_sonar.detect.calibrate import calibrate
from wifi_sonar.recording import Label, detector_states, load_labels, record_session, replay_states
from wifi_sonar.sources.simulated import ScenarioEvent, SimulatedSource


def test_replay_matches_the_live_detector(tmp_path) -> None:
    calibration = calibrate(
        SimulatedSource(seed=1, duration_s=10.0, n_subcarriers=8),
        seconds=10.0,
    )
    source = SimulatedSource(
        seed=6,
        duration_s=8.0,
        n_subcarriers=8,
        events=(ScenarioEvent("walk", 1.0, 4.0),),
    )
    labels = [Label(kind="walk", start_s=1.0, duration_s=4.0)]
    path = tmp_path / "session.jsonl"
    record_session(source, path, labels)
    live = detector_states(list(source.frames()), calibration)
    replayed = replay_states(path, calibration)
    assert replayed == live
    assert "motion" in replayed
    loaded = load_labels(path)
    assert loaded == labels
