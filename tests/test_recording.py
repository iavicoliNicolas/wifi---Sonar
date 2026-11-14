from fastapi.testclient import TestClient

from wifi_sonar.api.app import create_app
from wifi_sonar.detect.calibrate import calibrate
from wifi_sonar.detect.presence import analyze_frames
from wifi_sonar.engine import Engine
from wifi_sonar.models import CSIFrame
from wifi_sonar.recording import SessionRecorder, read_labels, save_recent
from wifi_sonar.settings import Settings
from wifi_sonar.sources.base import read_frames
from wifi_sonar.sources.replay import ReplaySource
from wifi_sonar.sources.simulated import SimConfig, SimEvent, SimulatedSource


def test_record_replay_keeps_the_detector_result(tmp_path):
    frames = SimulatedSource(
        SimConfig(
            seed=3,
            duration_s=28.0,
            events=(SimEvent("walk", 12.0, 8.0),),
        )
    ).generate()
    recorder = SessionRecorder(tmp_path)
    recorder.start("session")
    for frame in frames:
        recorder.write_frame(frame)
    recorder.label(12.0, "walk")
    path = recorder.stop()
    replayed = read_frames(ReplaySource(path, speed=0))
    baseline = calibrate(SimulatedSource(SimConfig(seed=1, duration_s=22.0)), seconds=20.0)
    _, _, original = analyze_frames(frames, 100.0, baseline)
    _, _, again = analyze_frames(replayed, 100.0, baseline)
    assert [sample.state for sample in original] == [sample.state for sample in again]
    assert [sample.moving for sample in original] == [sample.moving for sample in again]
    labels = read_labels(recorder.labels_path)
    assert labels == [{"ts": 12.0, "label": "walk"}]


def test_recording_endpoints(tmp_path):
    settings = Settings(auto_start=False, recordings_dir=str(tmp_path))
    engine = Engine(settings)
    app = create_app(settings, engine)
    with TestClient(app) as client:
        started = client.post("/recordings/start", json={"name": "demo"})
        assert started.status_code == 200
        assert (
            client.post("/recordings/label", json={"ts": 1.5, "label": "still"}).status_code == 200
        )
        stopped = client.post("/recordings/stop")
        assert stopped.status_code == 200
        assert read_labels(stopped.json()["labels"]) == [{"ts": 1.5, "label": "still"}]
        assert client.post("/recordings/stop").status_code == 409
        assert client.post("/recording").status_code == 409


def test_record_button_writes_frames_already_in_memory(tmp_path):
    settings = Settings(auto_start=False, recordings_dir=str(tmp_path))
    engine = Engine(settings)
    frames = [
        CSIFrame(timestamp=0.0, rssi=-40.0, amplitudes=(1.0, 2.0), node_id="living"),
        CSIFrame(timestamp=0.1, rssi=-41.0, amplitudes=(1.1, 2.1), node_id="living"),
        CSIFrame(timestamp=0.2, rssi=-39.0, amplitudes=(0.9, 1.9), node_id="pasillo"),
    ]
    for frame in frames:
        engine.remember(frame)
    assert engine.capture_from_recent is False
    path = save_recent(engine.recent_frames(), tmp_path)
    replayed = list(ReplaySource(path).frames())
    assert [(frame.timestamp, frame.node_id) for frame in replayed] == [
        (frame.timestamp, frame.node_id) for frame in frames
    ]
    client = TestClient(create_app(settings, engine))
    with client:
        saved = client.post("/recording")
    assert saved.status_code == 200
    body = saved.json()
    assert body["frames"] == 3
    assert (tmp_path / body["file"]).is_file()
