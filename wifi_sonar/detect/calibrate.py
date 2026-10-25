"""Baseline from an empty room: mean, deviation, and mean + k·σ thresholds."""

import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from wifi_sonar.detect.observe import observe
from wifi_sonar.pipeline.features import WindowFeatures
from wifi_sonar.sources.base import CSISource

FEATURE_NAMES = ("variance", "mean_abs_diff", "motion_energy", "breathing_energy")


@dataclass(frozen=True)
class Calibration:
    mean: dict[str, float]
    std: dict[str, float]
    thresholds: dict[str, float]
    k: float
    seconds: float

    def to_dict(self) -> dict[str, object]:
        return {
            "mean": self.mean,
            "std": self.std,
            "thresholds": self.thresholds,
            "k": self.k,
            "seconds": self.seconds,
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, object]) -> "Calibration":
        return cls(
            mean=_number_map(payload["mean"]),
            std=_number_map(payload["std"]),
            thresholds=_number_map(payload["thresholds"]),
            k=_number(payload["k"]),
            seconds=_number(payload["seconds"]),
        )


def calibrate(source: CSISource, seconds: float, *, k: float = 6.0) -> Calibration:
    """Capture ``seconds`` of an empty room and derive thresholds at mean + k·σ."""
    if seconds <= 0:
        raise ValueError("seconds must be positive")
    if k <= 0:
        raise ValueError("k must be positive")
    features = observe(source, seconds)
    if len(features) < 3:
        raise ValueError("need at least 3 windows to calibrate; record a longer empty trace")
    return calibration_from_features(features, k=k, seconds=seconds)


def quality_report(calibration: Calibration) -> dict[str, object]:
    """Say whether an empty-room capture looks usable.

    A short capture is ``corta``. A capture whose motion energy jumps (someone
    walked in halfway) is ``inestable``. A loud but steady capture is ``alta``:
    the room was probably not empty. Otherwise it is ``buena``.
    """
    mean = calibration.mean["motion_energy"]
    spread = calibration.std["motion_energy"] / max(abs(mean), 1e-12)
    if calibration.seconds < 8.0:
        label = "corta"
        detail = "la captura fue breve; repetila con la habitación vacía"
    elif spread > 0.8:
        label = "inestable"
        detail = "la señal cambió durante la captura; repetila con la habitación vacía"
    elif mean > 0.01:
        label = "alta"
        detail = "la línea base quedó alta; puede haber alguien en la habitación"
    else:
        label = "buena"
        detail = "el cuarto vacío quedó estable"
    return {
        "label": label,
        "detail": detail,
        "motion_spread": spread,
        "motion_mean": mean,
    }


def calibration_from_features(
    features: Sequence[WindowFeatures],
    *,
    k: float,
    seconds: float,
) -> Calibration:
    mean: dict[str, float] = {}
    std: dict[str, float] = {}
    thresholds: dict[str, float] = {}
    for name in FEATURE_NAMES:
        values = np.asarray([getattr(item, name) for item in features], dtype=np.float64)
        center = float(np.mean(values))
        spread = float(np.std(values))
        mean[name] = center
        std[name] = spread
        thresholds[name] = center + k * spread
    return Calibration(mean=mean, std=std, thresholds=thresholds, k=k, seconds=seconds)


def _number_map(value: object) -> dict[str, float]:
    if not isinstance(value, dict):
        raise ValueError("calibration section must be an object")
    return {key: _number(value[key]) for key in FEATURE_NAMES}


def _number(value: object) -> float:
    if isinstance(value, bool) or not isinstance(value, int | float):
        raise ValueError("calibration values must be numbers")
    return float(value)


def save_calibration(path: str | Path, calibration: Calibration) -> None:
    Path(path).write_text(json.dumps(calibration.to_dict(), indent=2) + "\n", encoding="utf-8")


def load_calibration(path: str | Path) -> Calibration:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    return Calibration.from_dict(payload)
