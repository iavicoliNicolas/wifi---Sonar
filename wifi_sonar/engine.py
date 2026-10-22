"""Une la fuente, el pipeline y los detectores. El panel solo ve el estado."""

from __future__ import annotations

import logging
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass, field

from wifi_sonar.detect.calibrate import Calibration, calibrate
from wifi_sonar.detect.motion import MotionConfig, MotionDetector
from wifi_sonar.detect.presence import PresenceConfig, PresenceMachine, PresenceState
from wifi_sonar.models import CSIFrame
from wifi_sonar.pipeline.features import extract_features
from wifi_sonar.pipeline.preprocess import preprocess
from wifi_sonar.settings import AppConfig, Settings
from wifi_sonar.sources.base import CSISource
from wifi_sonar.sources.simulated import SimConfig, SimulatedSource, demo_cycle
from wifi_sonar.storage.memory import MemoryStore

logger = logging.getLogger("wifi_sonar")
Listener = Callable[[dict[str, object]], None]


@dataclass
class NodeRuntime:
    buffer: list[CSIFrame] = field(default_factory=list)
    motion: MotionDetector | None = None
    presence: PresenceMachine | None = None
    last_feature_ts: float | None = None
    state: str = PresenceState.EMPTY
    score: float = 0.0
    presence_score: float = 0.0
    moving: bool = False
    ts: float = 0.0


@dataclass
class EngineStatus:
    state: str = PresenceState.EMPTY
    moving: bool = False
    score: float = 0.0
    presence_score: float = 0.0
    calibrated: bool = False
    paused: bool = False
    sensing: bool = False
    source: str = "sim"
    mode: str = "csi"
    node_id: str = ""
    ts: float | None = None
    connected: bool = False
    nodes: list[dict[str, object]] = field(default_factory=list)

    def as_dict(self) -> dict[str, object]:
        return {
            "state": self.state,
            "moving": self.moving,
            "score": self.score,
            "presence_score": self.presence_score,
            "calibrated": self.calibrated,
            "paused": self.paused,
            "sensing": self.sensing,
            "source": self.source,
            "mode": self.mode,
            "node_id": self.node_id,
            "ts": self.ts,
            "connected": self.connected,
            "nodes": self.nodes,
        }


class Engine:
    def __init__(
        self,
        settings: Settings,
        store: MemoryStore | None = None,
        source_factory: Callable[[], CSISource] | None = None,
        config: AppConfig | None = None,
    ) -> None:
        self.settings = settings
        self.store = store if store is not None else MemoryStore()
        self.source_factory = (
            source_factory if source_factory is not None else (lambda: build_source(settings))
        )
        self.config = config if config is not None else AppConfig()
        self._previous_ts: float | None = None
        self.calibration: Calibration | None = None
        self.nodes: dict[str, NodeRuntime] = {}
        self.connected = False
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._iterator = None
        self._listeners: list[Listener] = []
        self._pulled = 0
        saved = self.store.load_config()
        if saved:
            self.config = AppConfig(**saved)

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, name="wifi-sonar", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=2.0)
            self._thread = None

    def add_listener(self, listener: Listener) -> None:
        self._listeners.append(listener)

    def calibrate(self, seconds: float) -> Calibration:
        source = self._empty_source(seconds)
        calibration = calibrate(source, seconds=seconds, k=self.config.threshold_k)
        with self._lock:
            self.calibration = calibration
            self.nodes.clear()
            self.store.save_calibration(calibration.to_dict())
        logger.info("calibration saved", extra={"seconds": seconds})
        return calibration

    def update_config(self, updates: dict[str, object]) -> AppConfig:
        with self._lock:
            self.config = self.config.merged(updates)
            for node in self.nodes.values():
                node.motion = None
                node.presence = None
            self.store.save_config(self.config.to_dict())
            return self.config

    def ingest(self, frame: CSIFrame) -> None:
        """Procesa un frame ya leído. Si está en pausa, no entra al pipeline."""

        with self._lock:
            if self.config.paused:
                return
            node = self.nodes.setdefault(frame.node_id, NodeRuntime())
            node.buffer.append(frame)
            self._trim(node)
            node.ts = frame.timestamp
            self.connected = True
            if self.calibration is None:
                self._publish_locked()
                return
            needed = int(self.calibration.spectrum_window_s * self.calibration.sample_rate_hz)
            too_soon = (
                node.last_feature_ts is not None
                and frame.timestamp < node.last_feature_ts + self.config.step_s
            )
            if len(node.buffer) >= needed and not too_soon:
                self._update_node(node, frame.node_id)
            self._publish_locked()

    def step(self) -> bool:
        """Lee un frame de la fuente, salvo que el sensado esté en pausa.

        Devuelve False si no había frame. No avanza la fuente durante la pausa.
        """

        if self.config.paused:
            return False
        iterator = self._ensure_iterator()
        try:
            frame = next(iterator)
        except StopIteration:
            self._iterator = None
            self.connected = False
            return False
        self._pulled += 1
        self.ingest(frame)
        return True

    def status(self) -> dict[str, object]:
        with self._lock:
            return self._status_locked().as_dict()

    def _run(self) -> None:
        while not self._stop.is_set():
            if self.config.paused:
                self._stop.wait(0.05)
                continue
            try:
                iterator = self._ensure_iterator()
                frame = next(iterator)
            except StopIteration:
                self._iterator = None
                self.connected = False
                self._stop.wait(0.2)
                continue
            except Exception:
                logger.exception("source read failed")
                self._iterator = None
                self.connected = False
                self._stop.wait(0.2)
                continue
            self._pace(frame)
            self._pulled += 1
            self.ingest(frame)

    def _ensure_iterator(self):
        if self._iterator is None:
            source = self.source_factory()
            self._iterator = source.frames()
            self.connected = True
        return self._iterator

    def _pace(self, frame: CSIFrame) -> None:
        speed = self.settings.speed
        if speed <= 0 or self._previous_ts is None:
            self._previous_ts = frame.timestamp
            return
        delay = (frame.timestamp - self._previous_ts) / speed
        self._previous_ts = frame.timestamp
        if delay > 0:
            time.sleep(min(delay, 0.5))

    def _empty_source(self, seconds: float) -> CSISource:
        return SimulatedSource(
            SimConfig(
                seed=self.settings.seed + 17,
                duration_s=seconds + 1.0,
                noise_sigma=0.02,
                node_id="cal",
            )
        )

    def _trim(self, node: NodeRuntime) -> None:
        rate = 100.0
        keep = int((self.config.spectrum_window_s + 2.0) * rate)
        if len(node.buffer) > keep:
            del node.buffer[: len(node.buffer) - keep]

    def _update_node(self, node: NodeRuntime, node_id: str) -> None:
        assert self.calibration is not None
        cleaned = preprocess(node.buffer, self.calibration.sample_rate_hz)
        features = extract_features(
            cleaned, self.calibration.sample_rate_hz, self.calibration.feature_config()
        )
        if not features:
            return
        feature = features[-1]
        if node.last_feature_ts is not None and feature.timestamp <= node.last_feature_ts + 1e-9:
            return
        node.last_feature_ts = feature.timestamp
        if node.motion is None:
            node.motion = MotionDetector(self.calibration, self._motion_config())
        if node.presence is None:
            node.presence = PresenceMachine(self.calibration, self._presence_config())
        motion = node.motion.update(feature)
        sample = node.presence.update(feature, motion)
        changed = sample.state != node.state
        node.state = sample.state
        node.score = sample.score
        node.presence_score = sample.presence_score
        node.moving = sample.moving
        node.ts = sample.ts
        if changed:
            zone = self.config.zones.get(node_id, "")
            self.store.add_event(
                {
                    "ts": sample.ts,
                    "state": sample.state,
                    "score": sample.score,
                    "node_id": node_id,
                    "zone": zone,
                }
            )

    def _motion_config(self) -> MotionConfig:
        off = max(0.0, self.config.on_threshold - self.config.hysteresis)
        return MotionConfig(
            on_threshold=self.config.on_threshold,
            off_threshold=off,
            min_duration_s=self.config.min_duration_s,
            sensitivity=self.config.sensitivity,
        )

    def _presence_config(self) -> PresenceConfig:
        return PresenceConfig(
            min_duration_s=self.config.presence_min_duration_s,
            sensitivity=self.config.sensitivity,
        )

    def _status_locked(self) -> EngineStatus:
        states = [node.state for node in self.nodes.values()]
        fused = fuse_states(states, self.config.fusion)
        active = next(iter(self.nodes.values()), None)
        if active is not None:
            for node in self.nodes.values():
                if node.state == fused:
                    active = node
                    break
        node_rows = [
            {
                "node_id": node_id,
                "state": node.state,
                "score": node.score,
                "zone": self.config.zones.get(node_id, ""),
                "ts": node.ts,
            }
            for node_id, node in self.nodes.items()
        ]
        sensing = not self.config.paused
        return EngineStatus(
            state=fused if self.calibration is not None else PresenceState.EMPTY,
            moving=bool(active and active.moving),
            score=0.0 if active is None else active.score,
            presence_score=0.0 if active is None else active.presence_score,
            calibrated=self.calibration is not None,
            paused=self.config.paused,
            sensing=sensing,
            source=self.settings.source,
            mode=self.config.mode,
            node_id=""
            if active is None
            else next(
                (name for name, node in self.nodes.items() if node is active),
                "",
            ),
            ts=None if active is None else active.ts,
            connected=self.connected,
            nodes=node_rows,
        )

    def _publish_locked(self) -> None:
        snapshot = self._status_locked().as_dict()
        for listener in list(self._listeners):
            listener(snapshot)


def fuse_states(states: list[str], method: str) -> str:
    if not states:
        return PresenceState.EMPTY
    if method == "vote":
        ranking = (PresenceState.MOTION, PresenceState.PRESENCE, PresenceState.EMPTY)
        counts = {state: states.count(state) for state in ranking}
        top = max(counts.values())
        for state in ranking:
            if counts[state] == top:
                return state
    if any(state == PresenceState.MOTION for state in states):
        return PresenceState.MOTION
    if any(state == PresenceState.PRESENCE for state in states):
        return PresenceState.PRESENCE
    return PresenceState.EMPTY


def build_source(settings: Settings) -> CSISource:
    if settings.source == "sim":
        return SimulatedSource(
            SimConfig(
                seed=settings.seed,
                duration_s=None,
                loop=True,
                loop_period_s=40.0,
                events=demo_cycle(),
            )
        )
    raise ValueError(f"unsupported source: {settings.source}")
