import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from wifi_sonar.engine import Engine
from wifi_sonar.settings import Settings
from wifi_sonar.sources.simulated import SimConfig, SimEvent, SimulatedSource


def test_state_change_posts_to_the_local_webhook():
    received: list[dict] = []

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self) -> None:
            length = int(self.headers.get("content-length", "0"))
            received.append(json.loads(self.rfile.read(length)))
            self.send_response(204)
            self.end_headers()

        def log_message(self, _format: str, *args: object) -> None:
            return

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        port = server.server_address[1]
        engine = Engine(Settings(auto_start=False, seed=4))
        engine.calibrate(12)
        engine.update_config({"webhook_url": f"http://127.0.0.1:{port}/hook"})
        walk = SimulatedSource(
            SimConfig(seed=9, duration_s=18.0, events=(SimEvent("walk", 0.0, 18.0),))
        )
        for frame in walk.generate():
            engine.ingest(frame)
        deadline = threading.Event()
        for _ in range(30):
            if received:
                break
            deadline.wait(0.05)
        assert received
        assert received[0]["state"] == "movimiento"
        assert engine.config.sensitivity == 1.0
        engine.update_config({"sensitivity": 1.6, "window_s": 1.5, "hysteresis": 0.2})
        assert engine.config.sensitivity == 1.6
        assert engine.config.window_s == 1.5
        assert engine.config.hysteresis == 0.2
        saved = engine.store.load_config()
        assert saved is not None
        assert saved["sensitivity"] == 1.6
        assert saved["window_s"] == 1.5
        restored = Engine(Settings(auto_start=False, seed=4), store=engine.store)
        assert restored.config.webhook_url.endswith("/hook")
        assert restored.config.sensitivity == 1.6
    finally:
        server.shutdown()
