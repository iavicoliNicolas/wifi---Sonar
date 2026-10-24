"""Record a CSI session with manual labels and play it back through the same detector."""

import json
import time
from dataclasses import dataclass
from pathlib import Path

from wifi_sonar.detect.calibrate import Calibration
from wifi_sonar.detect.presence import PresenceDetector
from wifi_sonar.pipeline.features import extract_features
from wifi_sonar.pipeline.preprocess import preprocess
from wifi_sonar.sources.base import CSISource
from wifi_sonar.sources.frame import CSIFrame
from wifi_sonar.sources.listed import ListedSource
from wifi_sonar.sources.replay import ReplaySource, dump_jsonl


@dataclass(frozen=True)
class Label:
    kind: str
    start_s: float
    duration_s: float

    def to_dict(self) -> dict[str, object]:
        return {"kind": self.kind, "start_s": self.start_s, "duration_s": self.duration_s}


def save_recent(frames: list[CSIFrame], directory: str | Path) -> Path:
    """Write frames already in memory. This does not open a new capture."""
    if len(frames) < 2:
        raise ValueError("nothing to record")
    folder = Path(directory)
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / f"sesion-{time.time_ns()}.jsonl"
    record_session(ListedSource(frames), path, [])
    return path


def record_session(source: CSISource, path: str | Path, labels: list[Label]) -> None:
    """Write raw frames to ``path`` (JSONL) and labels to ``path`` + ``.labels.json``."""
    destination = Path(path)
    frames = list(source.frames())
    dump_jsonl(frames, destination)
    sidecar = destination.with_suffix(destination.suffix + ".labels.json")
    payload = [label.to_dict() for label in labels]
    sidecar.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def load_labels(path: str | Path) -> list[Label]:
    destination = Path(path)
    sidecar = destination.with_suffix(destination.suffix + ".labels.json")
    raw = json.loads(sidecar.read_text(encoding="utf-8"))
    labels = []
    for item in raw:
        labels.append(
            Label(kind=item["kind"], start_s=item["start_s"], duration_s=item["duration_s"])
        )
    return labels


def detector_states(frames: list[CSIFrame], calibration: Calibration) -> list[str]:
    detector = PresenceDetector(calibration)
    features = extract_features(preprocess(frames))
    return [detector.update(item).state for item in features]


def replay_states(path: str | Path, calibration: Calibration) -> list[str]:
    frames = list(ReplaySource(path, speed=0).frames())
    return detector_states(frames, calibration)
