import pytest
from fastapi.testclient import TestClient

from wifi_sonar.api.app import create_app
from wifi_sonar.engine import Engine, build_source
from wifi_sonar.settings import Settings
from wifi_sonar.sources.rssi import RssiConfig, RssiSource
from wifi_sonar.sources.simulated import SimEvent


def test_rssi_mode_needs_an_allow_list_and_does_not_invent_devices():
    with pytest.raises(ValueError, match="does not scan"):
        RssiSource(RssiConfig(devices=(" ",)))
    with pytest.raises(ValueError, match="does not scan"):
        build_source(Settings(source="rssi", rssi_devices=" , "))

    source = RssiSource(RssiConfig(devices=("telefono", "notebook"), seed=1, duration_s=0.2))
    frames = source.generate()
    assert {frame.node_id for frame in frames} == {"telefono", "notebook"}
    assert all(frame.n_subcarriers == 1 for frame in frames)


def _engine() -> Engine:
    return Engine(Settings(auto_start=False, source="rssi", seed=1, rssi_devices="telefono"))


def test_rssi_walk_is_motion_and_an_empty_room_stays_empty():
    quiet = _engine()
    assert quiet.config.mode == "rssi"
    quiet.calibrate(12)
    for frame in RssiSource(RssiConfig(devices=("telefono",), seed=8, duration_s=20.0)).generate():
        quiet.ingest(frame)
    assert quiet.status()["state"] == "vacío"

    moving = _engine()
    moving.calibrate(12)
    walk = RssiSource(
        RssiConfig(
            devices=("telefono",),
            seed=5,
            duration_s=18.0,
            events=(SimEvent("walk", 0.0, 18.0),),
        )
    )
    for frame in walk.generate():
        moving.ingest(frame)
    status = moving.status()
    assert status["state"] == "movimiento"
    assert status["mode"] == "rssi"
    assert status["nodes"][0]["node_id"] == "telefono"
    client = TestClient(create_app(moving.settings, moving))
    with client:
        assert "sensibilidad baja" in client.get("/").text
