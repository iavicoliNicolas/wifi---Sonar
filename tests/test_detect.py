from wifi_sonar.detect.calibrate import calibrate
from wifi_sonar.detect.motion import MotionDetector
from wifi_sonar.detect.observe import observe
from wifi_sonar.sources.simulated import ScenarioEvent, SimulatedSource


def _calibration():
    return calibrate(SimulatedSource(seed=1, duration_s=20.0), seconds=20.0, k=6.0)


def _episodes(samples) -> int:
    count = 0
    previous = False
    for sample in samples:
        if sample.moving and not previous:
            count += 1
        previous = sample.moving
    return count


def test_walks_are_detected_and_empty_room_stays_quiet() -> None:
    calibration = _calibration()
    gap = 6.0
    walk_s = 3.0
    events = []
    cursor = 8.0
    for _ in range(20):
        events.append(ScenarioEvent("walk", cursor, walk_s))
        cursor += walk_s + gap
    duration = cursor + 2.0
    features = observe(
        SimulatedSource(seed=7, duration_s=duration, events=tuple(events)),
    )
    detector = MotionDetector(calibration)
    samples = [detector.update(item) for item in features]
    assert all(0.0 <= sample.score <= 1.0 for sample in samples)
    detected = 0
    for event in events:
        end = event.start_s + event.duration_s
        hit = any(sample.moving and event.start_s <= sample.ts <= end + 1.5 for sample in samples)
        detected += int(hit)
        between = [sample for sample in samples if end + 1.5 < sample.ts < end + gap]
        assert any(not sample.moving for sample in between)
    assert detected >= 19

    empty = observe(SimulatedSource(seed=8, duration_s=600.0))
    quiet = MotionDetector(calibration)
    false_alarms = _episodes(quiet.update(item) for item in empty)
    assert false_alarms <= 1
