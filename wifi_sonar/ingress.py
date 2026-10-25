"""Optional UDP ingress for a board on this machine. Closed unless a port is set."""

import os
import threading
import time
from collections.abc import Callable

from fastapi import FastAPI

from wifi_sonar.api.stream import decimate
from wifi_sonar.detect.presence import PresenceDetector
from wifi_sonar.detect.zones import fuse_states, zone_states
from wifi_sonar.ops import iter_resilient
from wifi_sonar.pipeline.features import extract_features
from wifi_sonar.pipeline.preprocess import preprocess
from wifi_sonar.runtime import SonarState
from wifi_sonar.sources.base import CSISource
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


class _Track:
    """One receiver. Its buffer is not mixed with the other nodes."""

    def __init__(self) -> None:
        self.pending: list[CSIFrame] = []
        self.detector: PresenceDetector | None = None
        self.last_ts = -1.0
        self.since_eval = 0
        self.state = "empty"
        self.score = 0.0


class RollingSense:
    """One detector per node over the last 12 s. The room state is the fusion."""

    def __init__(self, state: SonarState) -> None:
        self.state = state
        self.tracks: dict[str, _Track] = {}
        self._config_token = ""

    def add(self, frame: CSIFrame) -> dict[str, object] | None:
        if self.state.paused:
            return None
        self.state.remember(frame)
        self.state.capture_from_recent = True
        track = self.tracks.setdefault(frame.node_id, _Track())
        if track.pending and frame.timestamp + 1e-6 < track.pending[-1].timestamp:
            track.pending.clear()
            track.detector = None
            track.last_ts = -1.0
            track.state = "empty"
            track.score = 0.0
        track.pending.append(frame)
        end = track.pending[-1].timestamp
        track.pending = [item for item in track.pending if item.timestamp >= end - _LOOKBACK_S]
        track.since_eval += 1
        if len(track.pending) < 2:
            return None
        if track.pending[-1].timestamp - track.pending[0].timestamp < _MIN_SPAN_S:
            return None
        if track.last_ts >= 0 and track.since_eval < 10:
            return None
        track.since_eval = 0
        self._evaluate(track)
        if track.last_ts < 0:
            return None
        latest = self.state.latest
        return {
            "ts": latest["ts"],
            "state": latest["state"],
            "score": latest["score"],
            "amplitudes": decimate(frame.amplitudes),
            "zones": self._zones(),
        }

    def _evaluate(self, track: _Track) -> None:
        token = self.state.config.model_dump_json()
        if token != self._config_token:
            self._config_token = token
            for item in self.tracks.values():
                item.detector = None
        if self.state.calibration is None:
            seconds = max(12.0, self.state.config.min_presence_s + 10.0)
            self.state.calibrate(seconds, allow_recent=False)
        if track.detector is None and self.state.calibration is not None:
            track.detector = PresenceDetector(
                self.state.calibration,
                hysteresis=self.state.config.hysteresis,
                min_motion_s=self.state.config.min_motion_s,
                min_presence_s=self.state.config.min_presence_s,
            )
        if track.detector is None:
            return
        for item in extract_features(preprocess(track.pending)):
            if item.timestamp <= track.last_ts:
                continue
            sample = track.detector.update(item)
            track.last_ts = item.timestamp
            track.state = sample.state
            track.score = sample.motion.score
            headline, score = self._headline()
            self.state._push(headline, score, sample.ts, stored_ts=time.time())

    def _headline(self) -> tuple[str, float]:
        mode = self.state.config.fusion
        headline = fuse_states([track.state for track in self.tracks.values()], mode)
        scores = [track.score for track in self.tracks.values() if track.state == headline]
        return headline, max(scores) if scores else 0.0

    def _zones(self) -> list[dict[str, str]]:
        mapping = {node_id: track.state for node_id, track in self.tracks.items()}
        zones = self.state.config.zones
        if not zones:
            headline, _score = self._headline()
            return [{"name": "esta habitación", "state": headline}]
        return zone_states(
            mapping,
            [(zone.name, zone.node_ids) for zone in zones],
            self.state.config.fusion,
        )


def consume_udp(app: FastAPI, open_source: Callable[[], CSISource], stop: threading.Event) -> None:
    """Read frames until ``stop``. A dropped link is retried; giving up marks the source down."""
    sense = RollingSense(app.state.sonar)
    try:
        for frame in iter_resilient(open_source):
            if stop.is_set():
                return
            snapshot = sense.add(frame)
            if snapshot is not None:
                app.state.hub.publish(snapshot)
    except ConnectionError:
        app.state.source_status = "down"


def start_udp(app: FastAPI, port: int) -> threading.Event:
    stop = threading.Event()
    app.state.source_status = "up"
    app.state.sonar.capture_from_recent = True

    def open_source() -> ESP32Source:
        return ESP32Source(udp_lines(port, stop=stop))

    threading.Thread(
        target=consume_udp,
        args=(app, open_source, stop),
        name="wifi-sonar-udp",
        daemon=True,
    ).start()
    return stop
