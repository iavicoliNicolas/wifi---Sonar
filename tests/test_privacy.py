from fastapi.testclient import TestClient
from wifi_sonar.api import create_app
from wifi_sonar.runtime import SonarConfig, SonarState
from wifi_sonar.sources.simulated import ScenarioEvent, SimulatedSource
from wifi_sonar.storage import Store


def test_pause_stops_ingestion(tmp_path) -> None:
    state = SonarState(config=SonarConfig(n_subcarriers=8), store=Store(tmp_path / "pause.sqlite"))
    state.paused = True
    state.calibrate(8)
    state.run(
        SimulatedSource(
            seed=3,
            duration_s=6.0,
            n_subcarriers=8,
            events=(ScenarioEvent("walk", 0.0, 6.0),),
        )
    )
    assert state.history == []
    assert state.latest["state"] == "empty"


def test_wipe_deletes_history(tmp_path) -> None:
    store = Store(tmp_path / "wipe.sqlite")
    state = SonarState(config=SonarConfig(n_subcarriers=8), store=store)
    client = TestClient(create_app(state))
    state.calibrate(8)
    state.run(
        SimulatedSource(
            seed=3,
            duration_s=6.0,
            n_subcarriers=8,
            events=(ScenarioEvent("walk", 0.0, 6.0),),
        )
    )
    assert client.get("/history").json()[-1]["state"] == "motion"
    cleared = client.delete("/history")
    assert cleared.status_code == 200
    assert client.get("/history").json() == []
    assert store.events() == []
    assert store.latest_calibration() is None
    status = client.get("/status").json()
    assert status["calibrated"] is False
    kept = client.get("/config").json()
    assert kept["retention_s"] == 7 * 24 * 3600


def test_pause_route_is_visible_on_status() -> None:
    client = TestClient(create_app(SonarState(config=SonarConfig(n_subcarriers=8))))
    paused = client.post("/sensing", json={"paused": True})
    assert paused.status_code == 200
    assert paused.json()["retention_s"] == 7 * 24 * 3600
    assert client.get("/status").json()["sensing"] is False
    client.post("/sensing", json={"paused": False})
    assert client.get("/status").json()["sensing"] is True
