import json
import logging
import socket
import time

from fastapi.testclient import TestClient

from wifi_sonar.api.app import create_app
from wifi_sonar.engine import Engine, build_source
from wifi_sonar.settings import Settings
from wifi_sonar.sources.esp32 import ESP32Source
from wifi_sonar.sources.simulated import SimConfig, SimEvent, SimulatedSource


def test_udp_stays_closed_without_the_env(monkeypatch):
    monkeypatch.delenv("WIFI_SONAR_UDP_PORT", raising=False)
    assert Settings.from_env().udp_port is None
    source = build_source(Settings(source="sim"))
    assert not isinstance(source, ESP32Source)
    opened = build_source(Settings(source="sim", udp_port=5500))
    assert isinstance(opened, ESP32Source)
    assert opened.udp_port == 5500


def test_short_trace_does_not_report_motion_until_the_window_fills():
    engine = Engine(Settings(auto_start=False, seed=3, source="file"))
    engine.calibrate(12)
    frames = SimulatedSource(
        SimConfig(
            seed=3,
            duration_s=16.0,
            events=(SimEvent("walk", 0.0, 16.0),),
        )
    ).generate()
    for frame in frames[:40]:
        engine.ingest(frame)
    assert engine.status()["state"] == "vacío"
    for frame in frames[40:]:
        engine.ingest(frame)
    assert engine.status()["state"] == "movimiento"


def test_repeated_drops_mark_the_source_down_and_the_api_stays_up():
    class _AlwaysDown:
        def __init__(self) -> None:
            self.calls = 0

        @property
        def sample_rate_hz(self) -> float:
            return 100.0

        def frames(self):
            self.calls += 1
            raise ConnectionError("udp socket closed")

    source = _AlwaysDown()
    engine = Engine(
        Settings(auto_start=False, source="esp32", speed=0),
        source_factory=lambda: source,
    )
    engine.start()
    try:
        deadline = time.monotonic() + 3.0
        while engine.source_status != "down" and time.monotonic() < deadline:
            time.sleep(0.05)
        assert engine.source_status == "down"
        calls = source.calls
        time.sleep(0.3)
        assert source.calls == calls
        client = TestClient(create_app(engine.settings, engine))
        with client:
            body = client.get("/health").json()
        assert body["ok"] is True
        assert body["source"] == "down"
    finally:
        engine.stop()


def test_a_dead_socket_reopens_and_parses_the_next_datagram(caplog):
    probe = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    probe.bind(("127.0.0.1", 0))
    port = probe.getsockname()[1]
    probe.close()
    made = {"n": 0}

    class _Proxy:
        def __init__(self, inner: socket.socket, *, dead: bool) -> None:
            self._inner = inner
            self._dead = dead

        def settimeout(self, value: float | None) -> None:
            self._inner.settimeout(value)

        def bind(self, address: tuple[str, int]) -> None:
            self._inner.bind(address)

        def recvfrom(self, bufsize: int, flags: int = 0):
            if self._dead:
                raise OSError(9, "Bad file descriptor")
            return self._inner.recvfrom(bufsize, flags)

        def close(self) -> None:
            self._inner.close()

    def factory(*args, **kwargs):
        made["n"] += 1
        inner = socket.socket(*args, **kwargs)
        return _Proxy(inner, dead=made["n"] == 1)

    def open_source() -> ESP32Source:
        return ESP32Source(
            udp_host="127.0.0.1",
            udp_port=port,
            socket_factory=factory,
        )

    engine = Engine(
        Settings(auto_start=False, source="esp32", speed=0),
        source_factory=open_source,
    )
    caplog.set_level(logging.INFO, logger="wifi_sonar")
    engine.start()
    sender = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    payload = b"CSI,living,1.0,-40,1|1|1\n"
    try:
        deadline = time.monotonic() + 3.0
        while engine._pulled < 1 and time.monotonic() < deadline:
            sender.sendto(payload, ("127.0.0.1", port))
            time.sleep(0.05)
    finally:
        engine.stop()
        sender.close()
    assert engine._pulled >= 1
    assert engine.status()["node_id"] == "living"
    assert made["n"] >= 2
    dropped = [
        json.loads(record.message) for record in caplog.records if record.name == "wifi_sonar"
    ]
    assert dropped and dropped[0]["event"] == "source dropped"
