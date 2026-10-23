"""Optional UDP ingress for a board on this machine. Closed unless a port is set."""

import os
import threading
import time

from fastapi import FastAPI

from wifi_sonar.api.stream import decimate
from wifi_sonar.detect.presence import PresenceDetector
from wifi_sonar.ops import iter_resilient
from wifi_sonar.pipeline.features import extract_features
from wifi_sonar.pipeline.preprocess import preprocess
from wifi_sonar.runtime import SonarState
from wifi_sonar.sources.esp32 import ESP32Source, udp_lines
from wifi_sonar.sources.frame import CSIFrame
from wifi_sonar.sources.listed import ListedSource

_LOOKBACK_S = 12.0
_MIN_SPAN_S = 2.0


def udp_port_from_env() -> int | None:
    raw = os.environ.get("WIFI_SONAR_UDP_PORT", "").strip()
    if not raw:
        return None
    port = int(raw)
    if port < 1 or port > 65535:
        raise ValueError("WIFI_SONAR_UDP_PORT must be between 1 and 65535")
    return port


def ingest_frames(state: SonarState, frames: list[CSIFrame]) -> None:
    """Remember a finished capture and run the detector over all of it.

    The automatic baseline stays the empty-room simulator. Short lists produce
    no windows: motion features need two seconds of trace.
    """
    if state.paused or not frames:
        return
    for frame in frames:
        state.remember(frame)
    state.capture_from_recent = True
    state.run(ListedSource(frames))


class RollingSense:
    """One detector over the last 12 s. Chunks shorter than 2 s do not decide."""

    def __init__(self, state: SonarState) -> None:
        self.state = state
        self.pending: list[CSIFrame] = []
        self.detector: PresenceDetector | None = None
        self.last_ts = -1.0
        self._since_eval = 0
        self._config_token = ""

    def add(self, frame: CSIFrame) -> dict[str, object] | None:
        if self.state.paused:
            return None
        self.state.remember(frame)
        self.state.capture_from_recent = True
        if self.pending and frame.timestamp + 1e-6 < self.pending[-1].timestamp:
            self.pending.clear()
            self.detector = None
            self.last_ts = -1.0
        self.pending.append(frame)
        end = self.pending[-1].timestamp
        self.pending = [item for item in self.pending if item.timestamp >= end - _LOOKBACK_S]
        self._since_eval += 1
        if len(self.pending) < 2:
            return None
        if self.pending[-1].timestamp - self.pending[0].timestamp < _MIN_SPAN_S:
            return None
        if self.last_ts >= 0 and self._since_eval < 10:
            return None
        self._since_eval = 0
        self._evaluate()
        if self.last_ts < 0:
            return None
        latest = self.state.latest
        return {
            "ts": latest["ts"],
            "state": latest["state"],
            "score": latest["score"],
            "amplitudes": decimate(frame.amplitudes),
            "zones": [{"name": "esta habitación", "state": str(latest["state"])}],
        }

    def _evaluate(self) -> None:
        token = self.state.config.model_dump_json()
        if token != self._config_token:
            self._config_token = token
            self.detector = None
        if self.state.calibration is None:
            seconds = max(12.0, self.state.config.min_presence_s + 10.0)
            self.state.calibrate(seconds, allow_recent=False)
        if self.detector is None and self.state.calibration is not None:
            self.detector = PresenceDetector(
                self.state.calibration,
                hysteresis=self.state.config.hysteresis,
                min_motion_s=self.state.config.min_motion_s,
                min_presence_s=self.state.config.min_presence_s,
            )
        if self.detector is None:
            return
        for item in extract_features(preprocess(self.pending)):
            if item.timestamp <= self.last_ts:
                continue
            sample = self.detector.update(item)
            self.last_ts = item.timestamp
            self.state._push(
                sample.state,
                sample.motion.score,
                sample.ts,
                stored_ts=time.time(),
            )


def start_udp(app: FastAPI, port: int) -> threading.Event:
    stop = threading.Event()
    app.state.source_status = "up"
    app.state.sonar.capture_from_recent = True
    sense = RollingSense(app.state.sonar)

    def open_source() -> ESP32Source:
        return ESP32Source(udp_lines(port, stop=stop))

    def loop() -> None:
        for frame in iter_resilient(open_source):
            if stop.is_set():
                return
            snapshot = sense.add(frame)
            if snapshot is not None:
                app.state.hub.publish(snapshot)

    threading.Thread(target=loop, name="wifi-sonar-udp", daemon=True).start()
    return stop
