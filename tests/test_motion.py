from wifi_sonar.detect.calibrate import Calibration, calibrate
from wifi_sonar.detect.motion import (
    MotionConfig,
    MotionDetector,
    detect_motion_in_frames,
    rising_edges,
)
from wifi_sonar.pipeline.features import FEATURE_NAMES, WindowFeatures
from wifi_sonar.sources.simulated import SimConfig, SimEvent, SimulatedSource


def _calibration() -> Calibration:
    zeros = dict.fromkeys(FEATURE_NAMES, 0.0)
    ones = dict.fromkeys(FEATURE_NAMES, 1.0)
    return Calibration(
        created_at="t",
        seconds=20.0,
        k=4.0,
        sample_rate_hz=100.0,
        mean=zeros,
        std=ones,
        thresholds={name: 4.0 for name in FEATURE_NAMES},
        window_s=2.0,
        step_s=0.5,
        spectrum_window_s=10.0,
    )


def _feature(timestamp: float, motion_energy: float) -> WindowFeatures:
    return WindowFeatures(timestamp, 0.0, 0.0, motion_energy, 0.0)


def test_hysteresis_ignores_a_spike_and_holds_a_sustained_score():
    detector = MotionDetector(_calibration(), MotionConfig(min_duration_s=1.0))
    # z = energy / std, score = z / k. energy 4 => score 1. energy 0 => score 0.
    spike = [
        detector.update(_feature(0.0, 0.0)),
        detector.update(_feature(0.5, 4.0)),
        detector.update(_feature(1.0, 0.0)),
    ]
    assert [sample.moving for sample in spike] == [False, False, False]

    held = MotionDetector(_calibration(), MotionConfig(min_duration_s=1.0))
    sustained = [held.update(_feature(step * 0.5, 4.0)) for step in range(5)]
    assert [sample.moving for sample in sustained] == [False, False, True, True, True]
    assert all(0.0 <= sample.score <= 1.0 for sample in sustained)

    released = [held.update(_feature(3.0 + step * 0.5, 0.0)) for step in range(4)]
    assert released[-1].moving is False
    assert released[-1].as_dict()["moving"] is False


def test_simulator_recall_and_false_positives():
    baseline = calibrate(
        SimulatedSource(SimConfig(seed=1, duration_s=25.0)),
        seconds=20.0,
        k=8.0,
    )
    empty = SimulatedSource(SimConfig(seed=2, duration_s=600.0)).generate()
    empty_motion = detect_motion_in_frames(empty, 100.0, baseline)
    assert len(rising_edges(empty_motion)) <= 1

    duration = 5.0
    gap = 18.0
    lead = 20.0
    count = 20
    events = tuple(
        SimEvent("walk", lead + index * (duration + gap), duration) for index in range(count)
    )
    total = lead + count * (duration + gap) + 12.0
    walked = SimulatedSource(SimConfig(seed=3, duration_s=total, events=events)).generate()
    motion = detect_motion_in_frames(walked, 100.0, baseline)
    hits = 0
    for event in events:
        window_end = event.start_s + event.duration_s + 10.0
        if any(sample.moving and event.start_s <= sample.ts <= window_end for sample in motion):
            hits += 1
    assert hits / count >= 0.95
