"""Presencia quieta y máquina de estados vacío / presencia / movimiento."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from enum import StrEnum

from wifi_sonar.detect.calibrate import Calibration
from wifi_sonar.detect.motion import MotionConfig, MotionSample, detect_motion
from wifi_sonar.models import CSIFrame
from wifi_sonar.pipeline.features import WindowFeatures, extract_features
from wifi_sonar.pipeline.preprocess import PreprocessConfig, preprocess


class PresenceState(StrEnum):
    EMPTY = "vacío"
    PRESENCE = "presencia"
    MOTION = "movimiento"


@dataclass(frozen=True, slots=True)
class PresenceConfig:
    on_threshold: float = 0.55
    off_threshold: float = 0.3
    min_duration_s: float = 3.0
    sensitivity: float = 1.0

    def __post_init__(self) -> None:
        if not 0.0 <= self.off_threshold <= self.on_threshold <= 1.0:
            raise ValueError("thresholds must satisfy 0 <= off <= on <= 1")
        if self.min_duration_s < 0:
            raise ValueError("min_duration_s must be >= 0")
        if self.sensitivity <= 0:
            raise ValueError("sensitivity must be positive")


@dataclass(frozen=True, slots=True)
class PresenceSample:
    ts: float
    state: str
    moving: bool
    score: float
    presence_score: float

    def as_dict(self) -> dict[str, float | bool | str]:
        return {
            "ts": self.ts,
            "state": self.state,
            "moving": self.moving,
            "score": self.score,
            "presence_score": self.presence_score,
        }


def presence_score(
    feature: WindowFeatures,
    calibration: Calibration,
    sensitivity: float = 1.0,
) -> float:
    spread = max(calibration.std["breath_energy"], 1e-12)
    z_score = (feature.breath_energy - calibration.mean["breath_energy"]) / spread
    scale = max(calibration.k, 1e-6) / max(sensitivity, 0.05)
    return float(min(1.0, max(0.0, z_score) / scale))


class PresenceMachine:
    """Movimiento gana. Si no, la banda de respiración sostenida marca presencia."""

    def __init__(
        self,
        calibration: Calibration,
        config: PresenceConfig | None = None,
    ) -> None:
        self.calibration = calibration
        self.config = config if config is not None else PresenceConfig()
        self.state = PresenceState.EMPTY
        self._high_since: float | None = None
        self._low_since: float | None = None

    def update(self, feature: WindowFeatures, motion: MotionSample) -> PresenceSample:
        breath = presence_score(feature, self.calibration, self.config.sensitivity)
        timestamp = feature.timestamp
        if motion.moving:
            self.state = PresenceState.MOTION
            self._high_since = None
            self._low_since = None
            return self._sample(timestamp, breath, motion)

        if self.state is PresenceState.MOTION:
            self.state = PresenceState.EMPTY
            self._high_since = None
            self._low_since = None

        if breath >= self.config.on_threshold:
            self._low_since = None
            if self._high_since is None:
                self._high_since = timestamp
            if timestamp - self._high_since >= self.config.min_duration_s:
                self.state = PresenceState.PRESENCE
        elif breath <= self.config.off_threshold:
            self._high_since = None
            if self._low_since is None:
                self._low_since = timestamp
            if (
                self.state is PresenceState.PRESENCE
                and timestamp - self._low_since >= self.config.min_duration_s
            ):
                self.state = PresenceState.EMPTY
        return self._sample(timestamp, breath, motion)

    def _sample(self, timestamp: float, breath: float, motion: MotionSample) -> PresenceSample:
        return PresenceSample(
            ts=timestamp,
            state=self.state.value,
            moving=motion.moving,
            score=motion.score,
            presence_score=breath,
        )


def detect_presence(
    features: Sequence[WindowFeatures],
    calibration: Calibration,
    motion: Sequence[MotionSample],
    config: PresenceConfig | None = None,
) -> list[PresenceSample]:
    if len(features) != len(motion):
        raise ValueError("features and motion samples must be aligned")
    machine = PresenceMachine(calibration, config)
    return [
        machine.update(feature, sample) for feature, sample in zip(features, motion, strict=True)
    ]


def analyze_frames(
    frames: Sequence[CSIFrame],
    sample_rate_hz: float,
    calibration: Calibration,
    motion_config: MotionConfig | None = None,
    presence_config: PresenceConfig | None = None,
    preprocess_config: PreprocessConfig | None = None,
) -> tuple[list[WindowFeatures], list[MotionSample], list[PresenceSample]]:
    cleaned = preprocess(frames, sample_rate_hz, preprocess_config)
    features = extract_features(cleaned, sample_rate_hz, calibration.feature_config())
    motion = detect_motion(features, calibration, motion_config)
    presence = detect_presence(features, calibration, motion, presence_config)
    return features, motion, presence
