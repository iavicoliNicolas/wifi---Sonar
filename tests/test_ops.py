import json
import logging

import numpy as np
from fastapi.testclient import TestClient
from wifi_sonar.api import create_app
from wifi_sonar.ops import iter_resilient, log_event
from wifi_sonar.runtime import SonarConfig, SonarState
from wifi_sonar.sources.frame import CSIFrame


def _frame(timestamp: float) -> CSIFrame:
    return CSIFrame(
        timestamp=timestamp,
        rssi=-50.0,
        amplitudes=np.ones(4),
        phases=None,
        node_id="sim-0",
    )


class _Flaky:
    def __init__(self, phase: int) -> None:
        self.phase = phase

    def frames(self):
        if self.phase == 1:
            yield _frame(1.0)
            raise ConnectionError("link down")
        yield _frame(2.0)
        yield _frame(3.0)


def test_a_dropped_source_resumes_and_the_api_stays_up(caplog) -> None:
    app = create_app(SonarState(config=SonarConfig(n_subcarriers=8)))
    client = TestClient(app)
    app.state.source_status = "reconnecting"
    assert client.get("/health").json()["ok"] is True
    phase = {"n": 0}

    def open_source() -> _Flaky:
        phase["n"] += 1
        return _Flaky(phase["n"])

    caplog.set_level(logging.INFO, logger="wifi_sonar")
    frames = list(iter_resilient(open_source, retries=2))
    app.state.source_status = "up"
    assert [frame.timestamp for frame in frames] == [1.0, 2.0, 3.0]
    health = client.get("/health").json()
    assert health == {"ok": True, "paused": False, "source": "up"}
    dropped = [
        json.loads(record.message) for record in caplog.records if record.name == "wifi_sonar"
    ]
    assert dropped[0]["event"] == "source dropped"
    assert dropped[0]["attempt"] == 1


def test_log_event_is_json(caplog) -> None:
    caplog.set_level(logging.INFO, logger="wifi_sonar")
    log_event("ready", port=8000)
    payload = json.loads(caplog.records[-1].message)
    assert payload == {"event": "ready", "port": 8000}


def test_idle_room_recalibrates_slowly() -> None:
    state = SonarState(config=SonarConfig(n_subcarriers=8))
    assert state.refresh_if_idle(30.0, every_s=120.0) is False
    state.latest["state"] = "motion"
    assert state.refresh_if_idle(500.0, every_s=120.0) is False
    state.latest["state"] = "empty"
    assert state.refresh_if_idle(120.0, every_s=120.0) is True
    assert state.calibration is not None
