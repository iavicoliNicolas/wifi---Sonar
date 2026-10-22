import json
import logging
import time

from fastapi.testclient import TestClient

from wifi_sonar.api.app import create_app
from wifi_sonar.engine import Engine
from wifi_sonar.jsonlog import JsonFormatter
from wifi_sonar.models import CSIFrame
from wifi_sonar.pipeline.features import WindowFeatures
from wifi_sonar.settings import Settings


class _FlakySource:
    def __init__(self) -> None:
        self.calls = 0

    @property
    def sample_rate_hz(self) -> float:
        return 100.0

    def frames(self):
        self.calls += 1
        if self.calls == 1:
            raise ConnectionError("cable unplugged")
        index = 0
        while True:
            index += 1
            yield CSIFrame(
                timestamp=index / 100.0,
                rssi=-40.0,
                amplitudes=(1.0, 0.5),
                node_id="nodo",
            )


def test_cutting_the_source_does_not_stop_the_service():
    source = _FlakySource()
    engine = Engine(
        Settings(auto_start=False, source="esp32", speed=0),
        source_factory=lambda: source,
    )
    engine.start()
    try:
        deadline = time.monotonic() + 3.0
        while engine._pulled < 1 and time.monotonic() < deadline:
            time.sleep(0.05)
        assert source.calls >= 2
        assert engine._pulled >= 1
        assert engine.status()["connected"] is True
    finally:
        engine.stop()


def test_health_and_json_logs():
    engine = Engine(Settings(auto_start=False, source="file"))
    client = TestClient(create_app(engine.settings, engine))
    with client:
        body = client.get("/health").json()
    assert body["ok"] is True
    assert body["sensing"] is True
    assert "version" in body

    line = JsonFormatter().format(
        logging.LogRecord("wifi_sonar", logging.INFO, __file__, 1, "hola", (), None)
    )
    payload = json.loads(line)
    assert payload["message"] == "hola"
    assert payload["level"] == "INFO"
    assert payload["logger"] == "wifi_sonar"


def test_empty_room_drift_is_slow_and_bounded():
    engine = Engine(Settings(auto_start=False, source="sim", seed=2))
    engine.calibrate(12)
    assert engine.calibration is not None
    anchor = engine.calibration.mean["motion_energy"]
    feature = WindowFeatures(
        timestamp=100.0,
        variance=0.0,
        mad=0.0,
        motion_energy=anchor + 10.0,
        breath_energy=engine.calibration.mean["breath_energy"],
    )
    engine._empty_since = 0.0
    engine._drift_baseline(feature)
    moved = engine.calibration.mean["motion_energy"]
    assert moved > anchor
    span = max(abs(anchor), engine.calibration.std["motion_energy"], 1e-6)
    assert moved <= anchor + 0.5 * span + 1e-9

    frozen = moved
    engine._empty_since = 90.0
    engine._drift_baseline(feature)
    assert engine.calibration.mean["motion_energy"] == frozen
