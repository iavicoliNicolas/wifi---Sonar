"""Turn a source into window features, optionally stopping after ``seconds``."""

from wifi_sonar.pipeline.features import WindowFeatures, extract_features
from wifi_sonar.pipeline.preprocess import preprocess
from wifi_sonar.sources.base import CSISource
from wifi_sonar.sources.frame import CSIFrame


def observe(source: CSISource, seconds: float | None = None) -> list[WindowFeatures]:
    frames: list[CSIFrame] = []
    for frame in source.frames():
        if seconds is not None and frame.timestamp > seconds:
            break
        frames.append(frame)
    if not frames:
        return []
    return extract_features(preprocess(frames))
