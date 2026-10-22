"""Precisión, recall y latencia sobre escenarios del simulador."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from wifi_sonar.detect.calibrate import calibrate
from wifi_sonar.detect.presence import PresenceState, analyze_frames
from wifi_sonar.sources.simulated import SimConfig, SimEvent, SimulatedSource

TAIL_S = 10.0


@dataclass(frozen=True, slots=True)
class Metric:
    scenario: str
    name: str
    value: float


def compute_metrics() -> list[Metric]:
    baseline = calibrate(SimulatedSource(SimConfig(seed=1, duration_s=25.0)), seconds=20.0)
    metrics: list[Metric] = []
    metrics.extend(_empty_metrics(baseline))
    metrics.extend(_motion_metrics(baseline))
    metrics.extend(_presence_metrics(baseline))
    return metrics


def render_report(metrics: list[Metric] | None = None) -> str:
    rows = metrics if metrics is not None else compute_metrics()
    lines = [
        "# Evaluación",
        "",
        "Pipeline sobre el simulador, con una calibración de 20 s en cuarto vacío (k = 8).",
        "La latencia es la mediana desde el inicio del evento hasta la primera detección.",
        "El espectro usa 10 s, así que la latencia incluye esa ventana.",
        "",
        "| Escenario | Métrica | Valor |",
        "| --- | --- | ---: |",
    ]
    for row in rows:
        lines.append(f"| {row.scenario} | {row.name} | {row.value:.3f} |")
    lines.append("")
    return "\n".join(lines)


def write_report(path: str | Path, metrics: list[Metric] | None = None) -> str:
    text = render_report(metrics)
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(text, encoding="utf-8")
    return text


def main() -> None:
    root = Path(__file__).resolve().parents[2]
    text = write_report(root / "docs" / "eval.md")
    print(text, end="")


def _empty_metrics(baseline) -> list[Metric]:
    frames = SimulatedSource(SimConfig(seed=21, duration_s=120.0)).generate()
    _, _, presence = analyze_frames(frames, 100.0, baseline)
    motion_fp = _rising(presence, lambda sample: sample.moving)
    presence_fp = _rising(presence, lambda sample: sample.state == PresenceState.PRESENCE)
    return [
        Metric("cuarto vacío 120 s", "falsos positivos de movimiento", float(len(motion_fp))),
        Metric("cuarto vacío 120 s", "falsos positivos de presencia", float(len(presence_fp))),
    ]


def _motion_metrics(baseline) -> list[Metric]:
    duration = 5.0
    gap = 18.0
    lead = 15.0
    count = 8
    events = tuple(
        SimEvent("walk", lead + index * (duration + gap), duration) for index in range(count)
    )
    total = lead + count * (duration + gap) + TAIL_S
    frames = SimulatedSource(SimConfig(seed=22, duration_s=total, events=events)).generate()
    _, _, presence = analyze_frames(frames, 100.0, baseline)
    intervals = [(event.start_s, event.start_s + event.duration_s + TAIL_S) for event in events]
    hits, latency = _hits(presence, intervals, lambda sample: sample.moving, events)
    false_positives = [
        sample
        for sample in _rising(presence, lambda sample: sample.moving)
        if not _inside(sample.ts, intervals)
    ]
    return [
        Metric("caminatas", "recall", hits / count),
        Metric("caminatas", "precisión", _precision(hits, len(false_positives))),
        Metric("caminatas", "latencia mediana (s)", latency),
    ]


def _presence_metrics(baseline) -> list[Metric]:
    events = (
        SimEvent("still", 12.0, 30.0),
        SimEvent("still", 60.0, 30.0),
    )
    frames = SimulatedSource(SimConfig(seed=23, duration_s=110.0, events=events)).generate()
    _, _, presence = analyze_frames(frames, 100.0, baseline)
    intervals = [(event.start_s, event.start_s + event.duration_s + 5.0) for event in events]
    hits, latency = _hits(
        presence,
        intervals,
        lambda sample: sample.state == PresenceState.PRESENCE,
        events,
    )
    false_positives = [
        sample
        for sample in _rising(presence, lambda sample: sample.state == PresenceState.PRESENCE)
        if not _inside(sample.ts, intervals)
    ]
    return [
        Metric("quietud", "recall", hits / len(events)),
        Metric("quietud", "precisión", _precision(hits, len(false_positives))),
        Metric("quietud", "latencia mediana (s)", latency),
    ]


def _hits(samples, intervals, active, events):
    delays: list[float] = []
    for event, interval in zip(events, intervals, strict=True):
        matched = [
            sample.ts
            for sample in samples
            if active(sample) and interval[0] <= sample.ts <= interval[1]
        ]
        if matched:
            delays.append(min(matched) - event.start_s)
    if not delays:
        return 0, 0.0
    ordered = sorted(delays)
    middle = ordered[len(ordered) // 2]
    return len(delays), middle


def _precision(hits: int, false_positives: int) -> float:
    total = hits + false_positives
    if total == 0:
        return 1.0
    return hits / total


def _rising(samples, active) -> list:
    found = []
    previous = False
    for sample in samples:
        current = bool(active(sample))
        if current and not previous:
            found.append(sample)
        previous = current
    return found


def _inside(timestamp: float, intervals: list[tuple[float, float]]) -> bool:
    return any(start <= timestamp <= end for start, end in intervals)
