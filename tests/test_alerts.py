import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

from fastapi.testclient import TestClient
from wifi_sonar.api import create_app
from wifi_sonar.runtime import SonarConfig, SonarState
from wifi_sonar.sources.simulated import ScenarioEvent, SimulatedSource


def test_webhook_must_stay_on_loopback() -> None:
    client = TestClient(create_app(SonarState(config=SonarConfig(n_subcarriers=8))))
    rejected = client.put(
        "/config",
        json={"webhook_url": "https://example.com/hook", "n_subcarriers": 8},
    )
    assert rejected.status_code == 422
    accepted = client.put(
        "/config",
        json={"webhook_url": "http://127.0.0.1:9/hook", "n_subcarriers": 8, "hysteresis": 0.2},
    )
    assert accepted.status_code == 200
    assert accepted.json()["webhook_url"] == "http://127.0.0.1:9/hook"
    assert accepted.json()["hysteresis"] == 0.2


def test_state_change_posts_the_loopback_webhook() -> None:
    received: list[dict[str, object]] = []

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self) -> None:
            length = int(self.headers.get("content-length", "0"))
            received.append(json.loads(self.rfile.read(length)))
            self.send_response(204)
            self.end_headers()

        def log_message(self, format: str, *args: object) -> None:
            return

    server = HTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    port = server.server_address[1]
    try:
        state = SonarState(
            config=SonarConfig(
                n_subcarriers=8,
                hysteresis=0.0,
                min_motion_s=0.0,
                webhook_url=f"http://127.0.0.1:{port}/hook",
            )
        )
        state.calibrate(8)
        state.run(
            SimulatedSource(
                seed=3,
                duration_s=6.0,
                n_subcarriers=8,
                events=(ScenarioEvent("walk", 0.0, 6.0),),
            )
        )
    finally:
        server.shutdown()
    assert any(item["state"] == "motion" for item in received)


def test_run_reads_the_config_in_effect() -> None:
    state = SonarState(config=SonarConfig(n_subcarriers=8, min_motion_s=0.0))
    state.calibrate(8)
    state.replace_config(state.config.model_copy(update={"min_motion_s": 30.0}))
    state.run(
        SimulatedSource(
            seed=3,
            duration_s=6.0,
            n_subcarriers=8,
            events=(ScenarioEvent("walk", 0.0, 6.0),),
        )
    )
    assert state.latest["state"] != "motion"
