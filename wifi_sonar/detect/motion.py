"""Detector de movimiento con histéresis y duración mínima."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from wifi_sonar.detect.calibrate import Calibration
from wifi_sonar.models import CSIFrame
from wifi_sonar.pipeline.features import WindowFeatures, extract_features
from wifi_sonar.pipeline.preprocess import PreprocessConfig, preprocess


@dataclass(frozen=True, slots=True)
class MotionConfig:
    on_threshold: float = 0.75
    off_threshold: float = 0.4
    min_duration_s: float = 1.0
    sensitivity: float = 1.0

    def __post_init__(self) -> None:
        if not 0.0 <= self.off_threshold <= self.on_threshold <= 1.0:
            raise ValueError("thresholds must satisfy 0 <= off <= on <= 1")
        if self.min_duration_s < 0:
            raise ValueError("min_duration_s must be >= 0")
        if self.sensitivity <= 0:
            raise ValueError("sensitivity must be positive")


@dataclass(frozen=True, slots=True)
class MotionSample:
    ts: float
    moving: bool
    score: float

    def as_dict(self) -> dict[str, float | bool]:
        return {"moving": self.moving, "score": self.score, "ts": self.ts}


def motion_score(
    feature: WindowFeatures, calibration: Calibration, sensitivity: float = 1.0
) -> float:
    """0 en la línea base y 1 cuando la energía de movimiento supera k·σ.

    Usa solo la banda 0.5–5 Hz. La varianza ancha también sube con la respiración
    y no sirve para separar caminar de estar quieto.
    """

    spread = max(calibration.std["motion_energy"], 1e-12)
    z_score = (feature.motion_energy - calibration.mean["motion_energy"]) / spread
    scale = max(calibration.k, 1e-6) / max(sensitivity, 0.05)
    raw = max(0.0, z_score) / scale
    return float(min(1.0, raw))


class MotionDetector:
    def __init__(self, calibration: Calibration, config: MotionConfig | None = None) -> None:
        self.calibration = calibration
        self.config = config if config is not None else MotionConfig()
        self.moving = False
        self._high_since: float | None = None
        self._low_since: float | None = None

    def update(self, feature: WindowFeatures) -> MotionSample:
        score = motion_score(feature, self.calibration, self.config.sensitivity)
        timestamp = feature.timestamp
        if not self.moving:
            if score >= self.config.on_threshold:
                if self._high_since is None:
                    self._high_since = timestamp
                held = timestamp - self._high_since
                if held >= self.config.min_duration_s:
                    self.moving = True
                    self._low_since = None
            else:
                self._high_since = None
        elif score <= self.config.off_threshold:
            if self._low_since is None:
                self._low_since = timestamp
            if timestamp - self._low_since >= self.config.min_duration_s:
                self.moving = False
                self._high_since = None
        else:
            self._low_since = None
        return MotionSample(ts=timestamp, moving=self.moving, score=score)


def detect_motion(
    features: Sequence[WindowFeatures],
    calibration: Calibration,
    config: MotionConfig | None = None,
) -> list[MotionSample]:
    detector = MotionDetector(calibration, config)
    return [detector.update(feature) for feature in features]


def detect_motion_in_frames(
    frames: Sequence[CSIFrame],
    sample_rate_hz: float,
    calibration: Calibration,
    config: MotionConfig | None = None,
    preprocess_config: PreprocessConfig | None = None,
) -> list[MotionSample]:
    cleaned = preprocess(frames, sample_rate_hz, preprocess_config)
    features = extract_features(cleaned, sample_rate_hz, calibration.feature_config())
    return detect_motion(features, calibration, config)


def rising_edges(samples: Sequence[MotionSample]) -> list[MotionSample]:
    edges: list[MotionSample] = []
    previous = False
    for sample in samples:
        if sample.moving and not previous:
            edges.append(sample)
        previous = sample.moving
    return edges
