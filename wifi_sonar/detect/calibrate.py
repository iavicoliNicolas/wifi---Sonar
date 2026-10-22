"""Línea base del cuarto vacío y umbrales media + k·σ."""

from __future__ import annotations

import json
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

import numpy as np

from wifi_sonar.models import CSIFrame
from wifi_sonar.pipeline.features import FEATURE_NAMES, FeatureConfig, extract_features
from wifi_sonar.pipeline.preprocess import PreprocessConfig, preprocess
from wifi_sonar.sources.base import CSISource


@dataclass(frozen=True, slots=True)
class Calibration:
    created_at: str
    seconds: float
    k: float
    sample_rate_hz: float
    mean: dict[str, float]
    std: dict[str, float]
    thresholds: dict[str, float]
    window_s: float
    step_s: float
    spectrum_window_s: float

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2, sort_keys=True)

    def to_dict(self) -> dict[str, object]:
        return {
            "created_at": self.created_at,
            "seconds": self.seconds,
            "k": self.k,
            "sample_rate_hz": self.sample_rate_hz,
            "mean": self.mean,
            "std": self.std,
            "thresholds": self.thresholds,
            "window_s": self.window_s,
            "step_s": self.step_s,
            "spectrum_window_s": self.spectrum_window_s,
        }

    @classmethod
    def from_json(cls, raw: str) -> Calibration:
        return cls.from_dict(json.loads(raw))

    @classmethod
    def from_dict(cls, payload: dict[str, object]) -> Calibration:
        return cls(
            created_at=str(payload["created_at"]),
            seconds=float(payload["seconds"]),  # type: ignore[arg-type]
            k=float(payload["k"]),  # type: ignore[arg-type]
            sample_rate_hz=float(payload["sample_rate_hz"]),  # type: ignore[arg-type]
            mean={key: float(value) for key, value in payload["mean"].items()},  # type: ignore[union-attr]
            std={key: float(value) for key, value in payload["std"].items()},  # type: ignore[union-attr]
            thresholds={
                key: float(value)
                for key, value in payload["thresholds"].items()  # type: ignore[union-attr]
            },
            window_s=float(payload["window_s"]),  # type: ignore[arg-type]
            step_s=float(payload["step_s"]),  # type: ignore[arg-type]
            spectrum_window_s=float(payload["spectrum_window_s"]),  # type: ignore[arg-type]
        )

    def feature_config(self) -> FeatureConfig:
        return FeatureConfig(
            window_s=self.window_s,
            step_s=self.step_s,
            spectrum_window_s=self.spectrum_window_s,
        )


def calibrate(
    source: CSISource,
    seconds: float,
    k: float = 8.0,
    path: str | Path | None = None,
    feature_config: FeatureConfig | None = None,
    preprocess_config: PreprocessConfig | None = None,
) -> Calibration:
    """Estima la línea base con `seconds` de ambiente vacío.

    El reloj es el de los frames, no el de pared: el simulador termina al instante.
    """

    if seconds <= 0:
        raise ValueError("seconds must be positive")
    if k < 0:
        raise ValueError("k must be >= 0")
    config = feature_config if feature_config is not None else FeatureConfig()
    if seconds < config.spectrum_window_s + config.step_s:
        raise ValueError("calibration must cover at least one full spectrum window")

    frames = collect_seconds(source, seconds)
    calibration = calibrate_frames(
        frames,
        source.sample_rate_hz,
        seconds=seconds,
        k=k,
        feature_config=config,
        preprocess_config=preprocess_config,
    )
    if path is not None:
        save_calibration(calibration, path)
    return calibration


def calibrate_frames(
    frames: Sequence[CSIFrame],
    sample_rate_hz: float,
    seconds: float,
    k: float = 8.0,
    feature_config: FeatureConfig | None = None,
    preprocess_config: PreprocessConfig | None = None,
) -> Calibration:
    config = feature_config if feature_config is not None else FeatureConfig()
    cleaned = preprocess(frames, sample_rate_hz, preprocess_config)
    features = extract_features(cleaned, sample_rate_hz, config)
    if len(features) < 2:
        raise ValueError("not enough windows to calibrate")

    mean: dict[str, float] = {}
    std: dict[str, float] = {}
    thresholds: dict[str, float] = {}
    for name in FEATURE_NAMES:
        values = np.array([getattr(feature, name) for feature in features], dtype=float)
        center = float(values.mean())
        spread = float(values.std(ddof=1))
        mean[name] = center
        std[name] = spread
        thresholds[name] = center + k * spread

    return Calibration(
        created_at=datetime.now(UTC).isoformat(),
        seconds=seconds,
        k=k,
        sample_rate_hz=sample_rate_hz,
        mean=mean,
        std=std,
        thresholds=thresholds,
        window_s=config.window_s,
        step_s=config.step_s,
        spectrum_window_s=config.spectrum_window_s,
    )


def collect_seconds(source: CSISource, seconds: float) -> list[CSIFrame]:
    frames: list[CSIFrame] = []
    started: float | None = None
    for frame in source.frames():
        if started is None:
            started = frame.timestamp
        frames.append(frame)
        if frame.timestamp - started >= seconds:
            return frames
    raise ValueError("source ended before the calibration window")


def save_calibration(calibration: Calibration, path: str | Path) -> None:
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(calibration.to_json() + "\n", encoding="utf-8")


def load_calibration(path: str | Path) -> Calibration:
    return Calibration.from_json(Path(path).read_text(encoding="utf-8"))
