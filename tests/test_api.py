from fastapi.testclient import TestClient
from wifi_sonar.api import create_app
from wifi_sonar.runtime import SonarConfig, SonarState
from wifi_sonar.sources.simulated import ScenarioEvent, SimulatedSource


def _client() -> TestClient:
    state = SonarState(config=SonarConfig(n_subcarriers=8))
    return TestClient(create_app(state))


def test_openapi_lists_the_endpoints() -> None:
    spec = _client().get("/openapi.json").json()
    paths = spec["paths"]
    for path in ("/status", "/calibrate", "/config", "/history"):
        assert path in paths


def test_config_roundtrip_and_validation() -> None:
    client = _client()
    put = client.put("/config", json={"hysteresis": 0.2, "k": 4.0, "n_subcarriers": 8})
    assert put.status_code == 200
    body = client.get("/config").json()
    assert body["hysteresis"] == 0.2
    assert body["k"] == 4.0
    rejected = client.put("/config", json={"hysteresis": 2.0})
    assert rejected.status_code == 422


def test_calibrate_status_and_history() -> None:
    client = _client()
    assert client.get("/status").json()["state"] == "empty"
    calibrated = client.post("/calibrate", json={"seconds": 8})
    assert calibrated.status_code == 200
    assert "motion_energy" in calibrated.json()["thresholds"]
    client.app.state.sonar.run(
        SimulatedSource(
            seed=3,
            duration_s=6.0,
            n_subcarriers=8,
            events=(ScenarioEvent("walk", 0.0, 6.0),),
        )
    )
    status = client.get("/status").json()
    assert status["state"] == "motion"
    assert status["calibrated"] is True
    history = client.get("/history").json()
    assert history[-1]["state"] == "motion"
