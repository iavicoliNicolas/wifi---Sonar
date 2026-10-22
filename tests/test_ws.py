from fastapi.testclient import TestClient

from wifi_sonar.api.app import create_app
from wifi_sonar.engine import Engine
from wifi_sonar.settings import Settings
from wifi_sonar.sources.simulated import SimConfig, SimEvent, SimulatedSource
from wifi_sonar.stream import SnapshotHub


def test_hub_drops_frames_nobody_read():
    hub = SnapshotHub()
    for index in range(50):
        hub.publish({"n": index})
    assert hub.dropped == 49
    assert hub.take() == {"n": 49}
    assert hub.take() is None


def test_websocket_receives_the_same_state_as_status():
    settings = Settings(auto_start=False, seed=4, speed=0)
    engine = Engine(settings)
    app = create_app(settings, engine)
    walk = SimulatedSource(
        SimConfig(seed=9, duration_s=18.0, events=(SimEvent("walk", 0.0, 18.0),))
    )
    with TestClient(app) as client:
        assert client.post("/calibrate", json={"seconds": 12}).status_code == 200
        for frame in walk.generate():
            engine.ingest(frame)
        with client.websocket_connect("/ws") as socket:
            message = socket.receive_json()
        status = client.get("/status").json()
        assert message["state"] == status["state"] == "movimiento"
        assert message["score"] == status["score"]
        assert message["features"]["motion_energy"] > 0
        assert message["amplitudes"]
