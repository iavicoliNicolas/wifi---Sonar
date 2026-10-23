import socket
import threading
import time

from wifi_sonar.ingress import RollingSense, ingest_frames, udp_port_from_env
from wifi_sonar.runtime import SonarConfig, SonarState
from wifi_sonar.sources.esp32 import ESP32Source, udp_lines
from wifi_sonar.sources.simulated import ScenarioEvent, SimulatedSource


def test_udp_stays_closed_without_the_env(monkeypatch) -> None:
    monkeypatch.delenv("WIFI_SONAR_UDP_PORT", raising=False)
    assert udp_port_from_env() is None


def test_a_datagram_becomes_a_frame() -> None:
    probe = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    probe.bind(("127.0.0.1", 0))
    port = probe.getsockname()[1]
    probe.close()
    stop = threading.Event()
    found: list[str] = []

    def read() -> None:
        for line in udp_lines(port, host="127.0.0.1", stop=stop):
            found.append(line)
            stop.set()

    thread = threading.Thread(target=read)
    thread.start()
    payload = b"CSI living 1.0 -40 1,1,1 -\n"
    sender = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        for _ in range(20):
            sender.sendto(payload, ("127.0.0.1", port))
            if found:
                break
            time.sleep(0.05)
    finally:
        stop.set()
        sender.close()
        thread.join(timeout=2)
    frames = list(ESP32Source(found).frames())
    assert frames and frames[0].node_id == "living"
    assert frames[0].rssi == -40


def test_ingest_runs_the_detector_on_a_batch() -> None:
    state = SonarState(config=SonarConfig(n_subcarriers=8))
    frames = list(
        SimulatedSource(
            seed=3,
            duration_s=6.0,
            n_subcarriers=8,
            events=(ScenarioEvent("walk", 0.0, 6.0),),
        ).frames()
    )
    ingest_frames(state, frames)
    assert state.capture_from_recent is True
    assert state.latest["state"] == "motion"
    assert state.calibration is not None


def test_short_chunks_need_two_seconds_then_report_motion() -> None:
    state = SonarState(config=SonarConfig(n_subcarriers=8))
    sense = RollingSense(state)
    frames = list(
        SimulatedSource(
            seed=3,
            duration_s=6.0,
            n_subcarriers=8,
            events=(ScenarioEvent("walk", 0.0, 6.0),),
        ).frames()
    )
    for frame in frames[:40]:
        assert sense.add(frame) is None
    assert state.calibration is None
    states = []
    for frame in frames[40:]:
        snapshot = sense.add(frame)
        if snapshot is not None:
            states.append(snapshot["state"])
    assert "motion" in states
    assert sense.detector is not None
