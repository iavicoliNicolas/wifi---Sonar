from fastapi.testclient import TestClient

from wifi_sonar.api.app import create_app
from wifi_sonar.engine import Engine, fuse_states
from wifi_sonar.settings import Settings
from wifi_sonar.sources.simulated import SimConfig, SimEvent, SimulatedSource


def _client() -> tuple[TestClient, Engine]:
    settings = Settings(auto_start=False, seed=4, speed=0)
    engine = Engine(settings)
    app = create_app(settings, engine)
    return TestClient(app), engine


def test_status_config_calibrate_history_and_openapi():
    client, engine = _client()
    with client:
        status = client.get("/status")
        assert status.status_code == 200
        body = status.json()
        assert body["calibrated"] is False
        assert body["state"] == "vacío"
        assert body["sensing"] is True

        config = client.get("/config")
        assert config.status_code == 200
        assert config.json()["sensitivity"] == 1.0

        updated = client.put("/config", json={"sensitivity": 1.4})
        assert updated.status_code == 200
        assert updated.json()["sensitivity"] == 1.4
        assert client.get("/config").json()["sensitivity"] == 1.4
        assert client.put("/config", json={"sensitivity": 9}).status_code == 422

        calibrated = client.post("/calibrate", json={"seconds": 12})
        assert calibrated.status_code == 200
        payload = calibrated.json()
        assert payload["k"] == 8.0
        assert "motion_energy" in payload["thresholds"]
        assert payload["quality"] in ("estable", "ruidosa")
        assert client.get("/status").json()["calibrated"] is True

        walk = SimulatedSource(
            SimConfig(seed=9, duration_s=18.0, events=(SimEvent("walk", 0.0, 18.0),))
        )
        for frame in walk.generate():
            engine.ingest(frame)
        assert client.get("/status").json()["state"] == "movimiento"
        history = client.get("/history").json()
        assert any(event["state"] == "movimiento" for event in history)

        spec = client.get("/openapi.json")
        assert spec.status_code == 200
        paths = spec.json()["paths"]
        for path in ("/status", "/calibrate", "/config", "/history"):
            assert path in paths


def test_panel_shell_is_served():
    client, _engine = _client()
    with client:
        page = client.get("/")
        assert page.status_code == 200
        assert "WiFi Sonar" in page.text
        assert 'id="state"' in page.text
        assert client.get("/assets/app.js").status_code == 200
        assert client.get("/assets/style.css").status_code == 200


def test_or_fusion_prefers_motion_and_vote_breaks_ties_toward_activity():
    assert fuse_states(["vacío", "movimiento"], "or") == "movimiento"
    assert fuse_states(["vacío", "presencia"], "or") == "presencia"
    assert fuse_states(["movimiento", "presencia"], "vote") == "movimiento"
