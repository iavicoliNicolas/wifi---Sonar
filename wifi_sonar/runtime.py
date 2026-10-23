"""In-memory sensing session shared by the HTTP API."""

from dataclasses import dataclass, field

from pydantic import BaseModel, Field

from wifi_sonar.detect.calibrate import Calibration, calibrate
from wifi_sonar.detect.observe import observe
from wifi_sonar.detect.presence import PresenceDetector
from wifi_sonar.sources.base import CSISource
from wifi_sonar.sources.simulated import SimulatedSource


class SonarConfig(BaseModel):
    hysteresis: float = Field(default=0.5, ge=0.0, lt=1.0)
    min_motion_s: float = Field(default=0.5, ge=0.0)
    min_presence_s: float = Field(default=2.0, ge=0.0)
    k: float = Field(default=6.0, gt=0.0)
    retention_s: int = Field(default=7 * 24 * 3600, ge=60)
    webhook_url: str | None = None
    sample_rate_hz: float = Field(default=50.0, gt=0.0)
    n_subcarriers: int = Field(default=52, ge=1, le=256)


@dataclass
class SonarState:
    config: SonarConfig = field(default_factory=SonarConfig)
    calibration: Calibration | None = None
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
        return self.calibration

    def run(self, source: CSISource) -> None:
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
            self.history.append({"ts": ts, "state": state, "score": score})
