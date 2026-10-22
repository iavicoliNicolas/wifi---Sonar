from fastapi.testclient import TestClient

from wifi_sonar.api.app import create_app
from wifi_sonar.detect.calibrate import calibrate
from wifi_sonar.detect.presence import analyze_frames
from wifi_sonar.engine import Engine
from wifi_sonar.recording import SessionRecorder, read_labels
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
