"""Replay de grabaciones CSV o JSONL, a velocidad real o acelerada."""

from __future__ import annotations

import csv
import json
import time
from collections.abc import Callable, Iterable, Iterator
from pathlib import Path

from wifi_sonar.models import CSIFrame

Sleep = Callable[[float], None]


def write_recording(path: str | Path, frames: Iterable[CSIFrame]) -> None:
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    suffix = destination.suffix.lower()
    if suffix == ".jsonl":
        lines = [dumps_frame(frame) for frame in frames]
        destination.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")
        return
    if suffix == ".csv":
        with destination.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.writer(handle)
            writer.writerow(["timestamp", "rssi", "node_id", "amplitudes", "phases"])
            for frame in frames:
                phases = "" if frame.phases is None else _join(frame.phases)
                writer.writerow(
                    [
                        repr(frame.timestamp),
                        repr(frame.rssi),
                        frame.node_id,
                        _join(frame.amplitudes),
                        phases,
                    ]
                )
        return
    raise ValueError(f"unsupported recording suffix: {destination.suffix}")


class ReplaySource:
    """Lee una grabación y la vuelve a emitir como `CSIFrame`.

    `speed=0` va tan rápido como se pueda. `speed=1` respeta los timestamps,
    `speed=2` los reproduce al doble.
    """

    def __init__(
        self,
        path: str | Path,
        speed: float = 0.0,
        sample_rate_hz: float | None = None,
        sleeper: Sleep = time.sleep,
    ) -> None:
        if speed < 0:
            raise ValueError("speed must be >= 0")
        self.path = Path(path)
        self.speed = speed
        self._sleeper = sleeper
        self._frames = load_recording(self.path)
        self._sample_rate_hz = (
            sample_rate_hz if sample_rate_hz is not None else infer_sample_rate(self._frames)
        )

    @property
    def sample_rate_hz(self) -> float:
        return self._sample_rate_hz

    def frames(self) -> Iterator[CSIFrame]:
        previous: CSIFrame | None = None
        for frame in self._frames:
            if previous is not None and self.speed > 0:
                delay = (frame.timestamp - previous.timestamp) / self.speed
                if delay > 0:
                    self._sleeper(delay)
            previous = frame
            yield frame


def load_recording(path: str | Path) -> list[CSIFrame]:
    source = Path(path)
    suffix = source.suffix.lower()
    if suffix == ".jsonl":
        return _load_jsonl(source)
    if suffix == ".csv":
        return _load_csv(source)
    raise ValueError(f"unsupported recording suffix: {source.suffix}")


def infer_sample_rate(frames: list[CSIFrame]) -> float:
    if len(frames) < 2:
        return 1.0
    deltas = [
        frames[index].timestamp - frames[index - 1].timestamp
        for index in range(1, len(frames))
        if frames[index].timestamp > frames[index - 1].timestamp
    ]
    if not deltas:
        return 1.0
    deltas.sort()
    median = deltas[len(deltas) // 2]
    return 1.0 / median


def dumps_frame(frame: CSIFrame) -> str:
    return json.dumps(_frame_payload(frame), ensure_ascii=False)


def _frame_payload(frame: CSIFrame) -> dict[str, object]:
    return {
        "timestamp": frame.timestamp,
        "rssi": frame.rssi,
        "amplitudes": list(frame.amplitudes),
        "phases": None if frame.phases is None else list(frame.phases),
        "node_id": frame.node_id,
    }


def _join(values: tuple[float, ...]) -> str:
    return "|".join(repr(value) for value in values)


def _split_floats(raw: str) -> tuple[float, ...]:
    if raw == "":
        return ()
    return tuple(float(part) for part in raw.split("|"))


def _load_jsonl(path: Path) -> list[CSIFrame]:
    frames: list[CSIFrame] = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            payload = json.loads(line)
            frames.append(_frame_from_mapping(payload))
        except (json.JSONDecodeError, KeyError, TypeError, ValueError) as error:
            raise ValueError(f"{path}:{line_number}: invalid CSI record") from error
    return frames


def _load_csv(path: Path) -> list[CSIFrame]:
    frames: list[CSIFrame] = []
    with path.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        for line_number, row in enumerate(reader, start=2):
            try:
                phases_raw = row.get("phases") or ""
                phases = _split_floats(phases_raw) if phases_raw else None
                frames.append(
                    CSIFrame(
                        timestamp=float(row["timestamp"]),
                        rssi=float(row["rssi"]),
                        amplitudes=_split_floats(row["amplitudes"]),
                        phases=phases,
                        node_id=row["node_id"],
                    )
                )
            except (KeyError, TypeError, ValueError) as error:
                raise ValueError(f"{path}:{line_number}: invalid CSI record") from error
    return frames


def _frame_from_mapping(payload: dict[str, object]) -> CSIFrame:
    phases_raw = payload["phases"]
    phases = None if phases_raw is None else tuple(float(value) for value in phases_raw)  # type: ignore[union-attr]
    amplitudes = tuple(float(value) for value in payload["amplitudes"])  # type: ignore[union-attr]
    return CSIFrame(
        timestamp=float(payload["timestamp"]),  # type: ignore[arg-type]
        rssi=float(payload["rssi"]),  # type: ignore[arg-type]
        amplitudes=amplitudes,
        phases=phases,
        node_id=str(payload["node_id"]),
    )
