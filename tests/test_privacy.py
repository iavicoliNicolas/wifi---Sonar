from fastapi.testclient import TestClient

from wifi_sonar.api.app import create_app
from wifi_sonar.engine import Engine
from wifi_sonar.models import CSIFrame
from wifi_sonar.settings import Settings


class _CountingSource:
    def __init__(self) -> None:
        self.pulled = 0

    @property
    def sample_rate_hz(self) -> float:
        return 100.0

    def frames(self):
        while True:
            self.pulled += 1
            yield CSIFrame(
                timestamp=self.pulled / 100.0,
                rssi=-40.0,
                amplitudes=(1.0, 0.2),
                node_id="sim-0",
            )


def test_pause_stops_ingestion_and_delete_clears_history():
    source = _CountingSource()
    settings = Settings(auto_start=False, source="file", speed=0)
    engine = Engine(settings, source_factory=lambda: source)
    engine.update_config({"paused": True})
    assert engine.step() is False
    assert source.pulled == 0
    engine.ingest(CSIFrame(timestamp=1.0, rssi=-40.0, amplitudes=(1.0, 0.2), node_id="sim-0"))
    assert engine.store.list_events() == []
    assert engine.status()["paused"] is True
    assert engine.status()["sensing"] is False

    engine.store.add_event(
        {"ts": 1.0, "state": "presencia", "score": 0.2, "node_id": "sim-0", "zone": ""}
    )
    client = TestClient(create_app(settings, engine))
    with client:
        page = client.get("/")
        assert "Sensado activo" in page.text
        assert "Borrar historial" in page.text
        deleted = client.delete("/history")
        assert deleted.status_code == 200
        assert client.get("/history").json() == []
        assert engine.store.list_events() == []
