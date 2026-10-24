from fastapi.testclient import TestClient
from wifi_sonar.api import create_app
from wifi_sonar.detect.calibrate import calibrate
from wifi_sonar.recording import Label, detector_states, load_labels, record_session, replay_states
from wifi_sonar.runtime import SonarConfig, SonarState
from wifi_sonar.sources.replay import ReplaySource
from wifi_sonar.sources.simulated import ScenarioEvent, SimulatedSource
from wifi_sonar.storage import Store


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


def test_post_saves_recent_frames_and_refuses_an_empty_buffer(tmp_path) -> None:
    state = SonarState(config=SonarConfig(n_subcarriers=8), store=Store(tmp_path / "sonar.sqlite"))
    client = TestClient(create_app(state))
    assert client.post("/recording").status_code == 409
    source = SimulatedSource(seed=2, duration_s=1.0, n_subcarriers=8)
    for frame in source.frames():
        state.remember(frame)
    saved = client.post("/recording")
    assert saved.status_code == 200
    body = saved.json()
    assert body["frames"] == len(source.frames())
    replay = list(ReplaySource(tmp_path / "recordings" / body["file"], speed=0).frames())
    assert [frame.timestamp for frame in replay] == [frame.timestamp for frame in source.frames()]
