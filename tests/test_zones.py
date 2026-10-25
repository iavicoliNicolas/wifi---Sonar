from fastapi.testclient import TestClient
from wifi_sonar.api import create_app
from wifi_sonar.detect.zones import fuse_states, zone_states
from wifi_sonar.runtime import SonarConfig, SonarState
from wifi_sonar.sources.simulated import ScenarioEvent, SimulatedSource


def _end_state(events: tuple[ScenarioEvent, ...]) -> str:
    state = SonarState(config=SonarConfig(n_subcarriers=8))
    state.calibrate(8)
    state.run(SimulatedSource(seed=3, duration_s=6.0, n_subcarriers=8, events=events, node_id="n"))
    return str(state.latest["state"])


def test_fusion_of_simulated_nodes() -> None:
    living = _end_state((ScenarioEvent("walk", 0.0, 6.0),))
    hall = _end_state(())
    assert living == "motion"
    assert hall == "empty"
    rows = zone_states(
        {"living": living, "hall": hall},
        [("casa", ["living", "hall"]), ("pasillo", ["hall"])],
    )
    assert rows == [
        {"name": "casa", "state": "motion"},
        {"name": "pasillo", "state": "empty"},
    ]
    assert fuse_states(["empty", "empty", "motion"], "vote") == "empty"
    assert fuse_states(["motion", "presence"], "vote") == "motion"
    assert fuse_states([], "or") == "empty"


def test_zone_config_roundtrip() -> None:
    client = TestClient(create_app(SonarState(config=SonarConfig(n_subcarriers=8))))
    body = client.get("/config").json()
    body["fusion"] = "vote"
    body["zones"] = [{"name": "pasillo", "node_ids": ["sim-0"]}]
    stored = client.put("/config", json=body)
    assert stored.status_code == 200
    assert stored.json()["fusion"] == "vote"
    assert stored.json()["zones"] == [{"name": "pasillo", "node_ids": ["sim-0"]}]
