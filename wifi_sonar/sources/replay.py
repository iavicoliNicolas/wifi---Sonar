"""Replay a recorded CSI trace from JSONL or CSV, at real time or faster."""

import csv
import json
import time
from collections.abc import Callable, Iterable, Iterator
from pathlib import Path

import numpy as np

from wifi_sonar.sources.frame import CSIFrame

Sleep = Callable[[float], None]
Clock = Callable[[], float]


def dump_jsonl(frames: Iterable[CSIFrame], path: str | Path) -> None:
    destination = Path(path)
    with destination.open("w", encoding="utf-8") as handle:
        for frame in frames:
            payload = {
                "timestamp": frame.timestamp,
                "rssi": frame.rssi,
                "amplitudes": frame.amplitudes.tolist(),
                "phases": None if frame.phases is None else frame.phases.tolist(),
                "node_id": frame.node_id,
            }
            handle.write(json.dumps(payload) + "\n")


def dump_csv(frames: Iterable[CSIFrame], path: str | Path) -> None:
    rows = list(frames)
    if not rows:
        raise ValueError("cannot write an empty CSV trace")
    n = rows[0].n_subcarriers
    has_phase = rows[0].phases is not None
    header = ["timestamp", "rssi", "node_id", *[f"amp{i}" for i in range(n)]]
    if has_phase:
        header.extend(f"phase{i}" for i in range(n))
    with Path(path).open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(header)
        for frame in rows:
            if frame.n_subcarriers != n or (frame.phases is not None) != has_phase:
                raise ValueError("every frame in a CSV trace needs the same layout")
            row: list[object] = [
                frame.timestamp,
                frame.rssi,
                frame.node_id,
                *frame.amplitudes.tolist(),
            ]
            if has_phase and frame.phases is not None:
                row.extend(frame.phases.tolist())
            writer.writerow(row)


def load_trace(path: str | Path) -> list[CSIFrame]:
    source = Path(path)
    suffix = source.suffix.lower()
    if suffix == ".jsonl":
        return list(_read_jsonl(source))
    if suffix == ".csv":
        return list(_read_csv(source))
    raise ValueError(f"unsupported trace format: {suffix}")


class ReplaySource:
    """File-backed ``CSISource``.

    ``speed <= 0`` yields as fast as the process can read. ``speed == 1`` follows
    the recorded timestamps. Larger values play faster by that factor.
    """

    def __init__(
        self,
        path: str | Path,
        *,
        speed: float = 0.0,
        sleep: Sleep = time.sleep,
        clock: Clock = time.perf_counter,
    ) -> None:
        self.path = Path(path)
        self.speed = speed
        self._sleep = sleep
        self._clock = clock
        self._frames = load_trace(self.path)

    def frames(self) -> Iterator[CSIFrame]:
        recorded = self._frames
        if self.speed <= 0 or len(recorded) < 2:
            yield from recorded
            return
        origin = self._clock()
        start = recorded[0].timestamp
        for frame in recorded:
            target = origin + (frame.timestamp - start) / self.speed
            delay = target - self._clock()
            if delay > 0:
                self._sleep(delay)
            yield frame


def _read_jsonl(path: Path) -> Iterator[CSIFrame]:
    with path.open(encoding="utf-8") as handle:
        for line_number, raw in enumerate(handle, start=1):
            text = raw.strip()
            if not text:
                continue
            try:
                payload = json.loads(text)
                phases = payload.get("phases")
                yield CSIFrame(
                    timestamp=float(payload["timestamp"]),
                    rssi=float(payload["rssi"]),
                    amplitudes=np.asarray(payload["amplitudes"], dtype=np.float64),
                    phases=None if phases is None else np.asarray(phases, dtype=np.float64),
                    node_id=str(payload["node_id"]),
                )
            except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
                raise ValueError(f"{path}:{line_number}: invalid CSI record") from exc


def _read_csv(path: Path) -> Iterator[CSIFrame]:
    with path.open(encoding="utf-8", newline="") as handle:
        reader = csv.reader(handle)
        try:
            header = next(reader)
        except StopIteration as exc:
            raise ValueError(f"{path}: empty CSV") from exc
        amp_idx = [i for i, name in enumerate(header) if name.startswith("amp")]
        phase_idx = [i for i, name in enumerate(header) if name.startswith("phase")]
        if not amp_idx:
            raise ValueError(f"{path}: CSV header needs amp0..ampN columns")
        try:
            ts_i = header.index("timestamp")
            rssi_i = header.index("rssi")
            node_i = header.index("node_id")
        except ValueError as exc:
            raise ValueError(f"{path}: CSV header needs timestamp, rssi, node_id") from exc
        for line_number, row in enumerate(reader, start=2):
            if not row or all(not cell.strip() for cell in row):
                continue
            try:
                phases = None
                if phase_idx:
                    phases = np.asarray([float(row[i]) for i in phase_idx], dtype=np.float64)
                yield CSIFrame(
                    timestamp=float(row[ts_i]),
                    rssi=float(row[rssi_i]),
                    amplitudes=np.asarray([float(row[i]) for i in amp_idx], dtype=np.float64),
                    phases=phases,
                    node_id=row[node_i],
                )
            except (IndexError, ValueError) as exc:
                raise ValueError(f"{path}:{line_number}: invalid CSI record") from exc
