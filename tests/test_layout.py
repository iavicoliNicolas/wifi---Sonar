import pytest
from fastapi.testclient import TestClient

from wifi_sonar.api.app import create_app
from wifi_sonar.engine import Engine, NodeRuntime
from wifi_sonar.settings import AppConfig, Settings


def test_layout_is_a_local_schematic_and_does_not_identify():
    settings = Settings(auto_start=False, source="file")
    engine = Engine(settings)
    node = engine.nodes.setdefault("living", NodeRuntime())
    node.state = "movimiento"
    node.motion = object()

    updated = engine.update_config({"layout": {"living": {"x": 0.25, "y": 0.8}}})
    assert updated.layout == {"living": {"x": 0.25, "y": 0.8}}
    assert engine.nodes["living"].motion is not None
    assert engine.nodes["living"].state == "movimiento"
    assert "trajectory" not in engine.status()

    with pytest.raises(ValueError, match="only stores x and y"):
        engine.update_config({"layout": {"living": {"x": 0.2, "y": 0.2, "name": "Ana"}}})
    assert engine.config.layout["living"]["y"] == 0.8

    with pytest.raises(ValueError, match="between 0 and 1"):
        engine.update_config({"layout": {"pasillo": {"x": 1.4, "y": 0.2}}})

    legacy = engine.config.to_dict()
    del legacy["layout"]
    assert AppConfig(**legacy).layout == {}

    client = TestClient(create_app(settings, engine))
    with client:
        assert client.get("/config").json()["layout"]["living"] == {"x": 0.25, "y": 0.8}
        rejected = client.put("/config", json={"layout": {"living": {"x": -0.1, "y": 0.2}}})
        assert rejected.status_code == 422
        assert client.get("/config").json()["layout"]["living"]["x"] == 0.25
