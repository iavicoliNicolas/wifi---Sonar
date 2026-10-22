"""Grabación de CSI crudo y etiquetas manuales, en el formato del replay."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

from wifi_sonar.models import CSIFrame
from wifi_sonar.sources.replay import dumps_frame


class SessionRecorder:
    def __init__(self, directory: str | Path) -> None:
        self.directory = Path(directory)
        self.path: Path | None = None
        self.labels_path: Path | None = None
        self._handle = None
        self.recording = False

    def start(self, name: str | None = None) -> Path:
        if self.recording:
            raise RuntimeError("a recording is already active")
        self.directory.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
        safe = name or stamp
        self.path = self.directory / f"{safe}.jsonl"
        self.labels_path = self.path.with_name(self.path.stem + ".labels.jsonl")
        self._handle = self.path.open("w", encoding="utf-8")
        self.labels_path.write_text("", encoding="utf-8")
        self.recording = True
        return self.path

    def write_frame(self, frame: CSIFrame) -> None:
        if not self.recording or self._handle is None:
            return
        self._handle.write(dumps_frame(frame) + "\n")

    def label(self, timestamp: float, label: str) -> None:
        if self.labels_path is None:
            raise RuntimeError("recording has not started")
        with self.labels_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps({"ts": timestamp, "label": label}) + "\n")

    def stop(self) -> Path:
        if not self.recording or self.path is None or self._handle is None:
            raise RuntimeError("recording is not active")
        self._handle.close()
        self._handle = None
        self.recording = False
        return self.path


def read_labels(path: str | Path) -> list[dict[str, object]]:
    source = Path(path)
    if not source.exists():
        return []
    labels: list[dict[str, object]] = []
    for line in source.read_text(encoding="utf-8").splitlines():
        if line.strip():
            labels.append(json.loads(line))
    return labels
