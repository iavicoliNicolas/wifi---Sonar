from fastapi.testclient import TestClient
from wifi_sonar.api import create_app
from wifi_sonar.api.stream import FrameHub, decimate, follow
from wifi_sonar.runtime import SonarConfig, SonarState
from wifi_sonar.sources.simulated import ScenarioEvent, SimulatedSource


def test_hub_drops_old_frames() -> None:
    hub = FrameHub(maxlen=2)
    queue = hub.subscribe()
    for index in range(5):
        hub.publish({"n": index})
    assert queue.get_nowait()["n"] == 3
    assert queue.get_nowait()["n"] == 4
    assert queue.empty()


def test_decimate_collapses_subcarriers() -> None:
    reduced = decimate([float(index) for index in range(52)], bins=8)
    assert len(reduced) == 8
    assert reduced[0] < reduced[-1]


def test_follow_emits_about_ten_hertz_and_ends_in_motion() -> None:
    state = SonarState(config=SonarConfig(n_subcarriers=8))
    state.calibrate(8)
    source = SimulatedSource(
        seed=3,
        duration_s=4.0,
        n_subcarriers=8,
        events=(ScenarioEvent("walk", 0.0, 4.0),),
    )
    snapshots = follow(state, source, hz=10.0, bins=8)
    assert 35 <= len(snapshots) <= 45
    assert len(snapshots[-1]["amplitudes"]) == 8
    assert snapshots[-1]["state"] == "motion"


def test_follow_stores_wall_time_and_keeps_trace_time_on_the_snapshot() -> None:
    state = SonarState(config=SonarConfig(n_subcarriers=8))
    state.calibrate(8)
    source = SimulatedSource(
        seed=3,
        duration_s=4.0,
        n_subcarriers=8,
        events=(ScenarioEvent("walk", 0.0, 4.0),),
    )
    wall = 1_700_000_000.0
    snapshots = follow(state, source, hz=10.0, stored_clock=lambda: wall)
    assert snapshots[0]["ts"] < 10
    assert state.history[0]["ts"] == wall
    assert state.latest["ts"] == snapshots[-1]["ts"]


def test_websocket_receives_a_coherent_state() -> None:
    app = create_app(SonarState(config=SonarConfig(n_subcarriers=8)))
    client = TestClient(app)
    with client.websocket_connect("/ws") as socket:
        app.state.hub.publish(
            {"ts": 1.0, "state": "presence", "score": 0.4, "amplitudes": [1.0, 2.0]}
        )
        payload = socket.receive_json()
    assert payload["state"] == "presence"
    assert payload["score"] == 0.4
    assert payload["amplitudes"] == [1.0, 2.0]


def test_queue_drop_replaces_the_only_slot() -> None:
    hub = FrameHub(maxlen=1)
    queue = hub.subscribe()
    hub.publish({"n": 1})
    hub.publish({"n": 2})
    assert queue.get_nowait()["n"] == 2
