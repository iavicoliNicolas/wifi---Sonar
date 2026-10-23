"""Optional UDP ingress for a board on this machine. Closed unless a port is set."""

import os
import threading

from fastapi import FastAPI

from wifi_sonar.ops import iter_resilient
from wifi_sonar.runtime import SonarState
from wifi_sonar.sources.esp32 import ESP32Source, udp_lines
from wifi_sonar.sources.frame import CSIFrame
from wifi_sonar.sources.listed import ListedSource


def udp_port_from_env() -> int | None:
    raw = os.environ.get("WIFI_SONAR_UDP_PORT", "").strip()
    if not raw:
        return None
    port = int(raw)
    if port < 1 or port > 65535:
        raise ValueError("WIFI_SONAR_UDP_PORT must be between 1 and 65535")
    return port


def ingest_frames(state: SonarState, frames: list[CSIFrame]) -> None:
    """Remember the batch and run the detector. The automatic baseline stays simulated."""
    if state.paused or not frames:
        return
    for frame in frames:
        state.remember(frame)
    state.capture_from_recent = True
    state.run(ListedSource(frames))


def start_udp(app: FastAPI, port: int) -> threading.Event:
    stop = threading.Event()
    app.state.source_status = "up"
    app.state.sonar.capture_from_recent = True

    def open_source() -> ESP32Source:
        return ESP32Source(udp_lines(port, stop=stop))

    def loop() -> None:
        batch: list[CSIFrame] = []
        for frame in iter_resilient(open_source):
            if stop.is_set():
                return
            batch.append(frame)
            if len(batch) < 50:
                continue
            ingest_frames(app.state.sonar, batch)
            latest = app.state.sonar.latest
            app.state.hub.publish(
                {
                    "ts": latest["ts"],
                    "state": latest["state"],
                    "score": latest["score"],
                    "amplitudes": [],
                    "zones": [{"name": "esta habitación", "state": str(latest["state"])}],
                }
            )
            batch = []

    threading.Thread(target=loop, name="wifi-sonar-udp", daemon=True).start()
    return stop
