"""Sensing session shared by the HTTP API. Optional SQLite keeps it across restarts."""

import json
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from typing import Any, Literal
from urllib.parse import urlparse

from pydantic import BaseModel, Field, field_validator

from wifi_sonar.detect.calibrate import Calibration, calibrate
from wifi_sonar.detect.observe import observe
from wifi_sonar.detect.presence import PresenceDetector
from wifi_sonar.sources.base import CSISource
from wifi_sonar.sources.simulated import SimulatedSource


class ZoneSpec(BaseModel):
    name: str = Field(min_length=1, max_length=40)
    node_ids: list[str] = Field(default_factory=list)


class SonarConfig(BaseModel):
    hysteresis: float = Field(default=0.5, ge=0.0, lt=1.0)
    min_motion_s: float = Field(default=0.5, ge=0.0)
    min_presence_s: float = Field(default=2.0, ge=0.0)
    k: float = Field(default=6.0, gt=0.0)
    retention_s: int = Field(default=7 * 24 * 3600, ge=60)
    webhook_url: str | None = None
    sample_rate_hz: float = Field(default=50.0, gt=0.0)
    n_subcarriers: int = Field(default=52, ge=1, le=256)
    fusion: Literal["or", "vote"] = "or"
    zones: list[ZoneSpec] = Field(default_factory=list)

    @field_validator("webhook_url")
    @classmethod
    def webhook_stays_on_this_machine(cls, value: str | None) -> str | None:
        if value is None or value == "":
            return None
        parsed = urlparse(value)
        host = parsed.hostname
        if parsed.scheme != "http" or host not in {"127.0.0.1", "localhost"}:
            raise ValueError("webhook_url must be an http URL on 127.0.0.1 or localhost")
        return value


@dataclass
class SonarState:
    config: SonarConfig = field(default_factory=SonarConfig)
    calibration: Calibration | None = None
    store: Any | None = None
    paused: bool = False
    latest: dict[str, object] = field(
        default_factory=lambda: {
            "state": "empty",
            "score": 0.0,
            "ts": 0.0,
            "sensing": True,
            "calibrated": False,
        }
    )
    history: list[dict[str, object]] = field(default_factory=list)

    def __post_init__(self) -> None:
        if self.store is None:
            return
        raw_config = self.store.load_config()
        if raw_config:
            self.config = SonarConfig.model_validate_json(raw_config)
        saved = self.store.latest_calibration()
        if saved is not None:
            self.calibration = saved
            self.latest["calibrated"] = True
        self.history = self.store.events()

    def replace_config(self, config: SonarConfig) -> None:
        self.config = config
        if self.store is not None:
            self.store.save_config(config.model_dump_json())

    def wipe(self) -> None:
        self.history.clear()
        self.calibration = None
        self.latest = {
            "state": "empty",
            "score": 0.0,
            "ts": 0.0,
            "sensing": not self.paused,
            "calibrated": False,
        }
        if self.store is not None:
            self.store.clear()

    def purge(self, now: float) -> int:
        if self.store is None:
            cutoff = now - self.config.retention_s
            before = len(self.history)
            self.history = [item for item in self.history if float(item["ts"]) >= cutoff]
            return before - len(self.history)
        removed = int(self.store.purge(self.config.retention_s, now))
        self.history = self.store.events()
        return removed

    def calibrate(self, seconds: float) -> Calibration:
        if seconds <= 0:
            raise ValueError("seconds must be positive")
        source = SimulatedSource(
            seed=1,
            duration_s=seconds,
            sample_rate_hz=self.config.sample_rate_hz,
            n_subcarriers=self.config.n_subcarriers,
        )
        self.calibration = calibrate(source, seconds, k=self.config.k)
        self.latest["calibrated"] = True
        if self.store is not None:
            self.store.save_calibration(self.calibration)
        return self.calibration

    def run(self, source: CSISource) -> None:
        self.purge(self._now())
        if self.calibration is None:
            self.calibrate(max(12.0, self.config.min_presence_s + 10.0))
        detector = PresenceDetector(
            self.calibration,
            hysteresis=self.config.hysteresis,
            min_motion_s=self.config.min_motion_s,
            min_presence_s=self.config.min_presence_s,
        )
        for features in observe(source):
            if self.paused:
                break
            sample = detector.update(features)
            self._push(sample.state, sample.motion.score, sample.ts)

    def _push(self, state: str, score: float, ts: float) -> None:
        self.latest = {
            "state": state,
            "score": score,
            "ts": ts,
            "sensing": not self.paused,
            "calibrated": self.calibration is not None,
        }
        if not self.history or self.history[-1]["state"] != state:
            event = {"ts": ts, "state": state, "score": score}
            self.history.append(event)
            if self.store is not None:
                self.store.add_event(ts, state, score)
            self._notify(event)

    def _notify(self, event: dict[str, object]) -> None:
        url = self.config.webhook_url
        if not url:
            return
        payload = json.dumps(event).encode("utf-8")
        request = urllib.request.Request(
            url,
            data=payload,
            headers={"content-type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=0.5) as response:
                response.read()
        except (urllib.error.URLError, TimeoutError, OSError):
            return

    def _now(self) -> float:
        if self.history:
            return float(self.history[-1]["ts"])
        return 0.0
