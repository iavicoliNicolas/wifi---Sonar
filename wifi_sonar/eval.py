"""Run the pipeline on scripted scenarios and report precision, recall, and latency."""

from dataclasses import dataclass
from pathlib import Path

from wifi_sonar.detect.calibrate import calibrate
from wifi_sonar.detect.observe import observe
from wifi_sonar.detect.presence import PresenceDetector, PresenceSample
from wifi_sonar.sources.simulated import ScenarioEvent, SimulatedSource

GRACE_S = 1.5


@dataclass(frozen=True)
class ClassMetrics:
    name: str
    precision: float
    recall: float
    latency_s: float
    tp: int
    fp: int
    expected: int


def evaluate(path: Path | None = None) -> str:
    calibration = calibrate(SimulatedSource(seed=1, duration_s=16.0), seconds=16.0, k=6.0)
    walks, stills = _scenario()
    rows = (
        _metrics(*_run(walks, calibration), "motion", "walk"),
        _metrics(*_run(stills, calibration), "presence", "still"),
    )
    report = _render(rows)
    if path is not None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(report, encoding="utf-8")
    return report


def _scenario() -> tuple[list[ScenarioEvent], list[ScenarioEvent]]:
    walks: list[ScenarioEvent] = []
    cursor = 6.0
    for _ in range(10):
        walks.append(ScenarioEvent("walk", cursor, 3.0))
        cursor += 9.0
    stills: list[ScenarioEvent] = []
    cursor = 6.0
    for _ in range(4):
        stills.append(ScenarioEvent("still", cursor, 16.0))
        cursor += 24.0
    return walks, stills


def _run(
    events: list[ScenarioEvent],
    calibration,
) -> tuple[list[PresenceSample], list[ScenarioEvent]]:
    duration = max(event.start_s + event.duration_s for event in events) + 4.0
    features = observe(SimulatedSource(seed=5, duration_s=duration, events=tuple(events)))
    detector = PresenceDetector(calibration)
    return [detector.update(item) for item in features], events


def _metrics(
    samples: list[PresenceSample],
    events: list[ScenarioEvent],
    state: str,
    kind: str,
) -> ClassMetrics:
    relevant = [event for event in events if event.kind == kind]
    latencies: list[float] = []
    tp = 0
    for event in relevant:
        end = event.start_s + event.duration_s + GRACE_S
        hits = [
            sample
            for sample in samples
            if sample.state == state and event.start_s <= sample.ts <= end
        ]
        if hits:
            tp += 1
            latencies.append(hits[0].ts - event.start_s)
    fp = 0
    previous = False
    for sample in samples:
        active = sample.state == state
        if active and not previous and not _inside(sample.ts, relevant):
            fp += 1
        previous = active
    expected = len(relevant)
    precision = tp / (tp + fp) if tp + fp else 1.0
    recall = tp / expected if expected else 1.0
    latency = sum(latencies) / len(latencies) if latencies else 0.0
    return ClassMetrics(state, precision, recall, latency, tp, fp, expected)


def _inside(timestamp: float, events: list[ScenarioEvent]) -> bool:
    for event in events:
        end = event.start_s + event.duration_s + GRACE_S
        if event.start_s <= timestamp <= end:
            return True
    return False


def _render(rows: tuple[ClassMetrics, ...]) -> str:
    lines = [
        "# Evaluación",
        "",
        "Escenario sintético: 10 caminatas de 3 s y 4 quietudes de 16 s,",
        "separadas por cuarto vacío. La latencia es el promedio desde el",
        "inicio del evento hasta la primera muestra del estado correcto.",
        "",
        "| Clase | Precisión | Recall | Latencia (s) | TP | FP | Esperados |",
        "| --- | --- | --- | --- | --- | --- | --- |",
    ]
    for row in rows:
        lines.append(
            f"| {row.name} | {row.precision:.3f} | {row.recall:.3f} | {row.latency_s:.2f} "
            f"| {row.tp} | {row.fp} | {row.expected} |"
        )
    lines.append("")
    return "\n".join(lines)


def main() -> None:
    report = evaluate(Path("docs/eval.md"))
    print(report, end="")


if __name__ == "__main__":
    main()
