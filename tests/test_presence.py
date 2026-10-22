from wifi_sonar.detect.calibrate import Calibration, calibrate
from wifi_sonar.detect.motion import MotionSample
from wifi_sonar.detect.presence import (
    PresenceConfig,
    PresenceMachine,
    PresenceState,
    analyze_frames,
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


def _breath(timestamp: float, energy: float) -> WindowFeatures:
    return WindowFeatures(timestamp, 0.0, 0.0, 0.0, energy)


def _still(timestamp: float, moving: bool = False, score: float = 0.0) -> MotionSample:
    return MotionSample(ts=timestamp, moving=moving, score=score)


def test_state_machine_empty_presence_and_motion():
    machine = PresenceMachine(_calibration(), PresenceConfig(min_duration_s=3.0))
    assert machine.update(_breath(0.0, 0.0), _still(0.0)).state == PresenceState.EMPTY

    spike = machine.update(_breath(1.0, 10.0), _still(1.0))
    assert spike.state == PresenceState.EMPTY
    assert machine.update(_breath(2.0, 0.0), _still(2.0)).state == PresenceState.EMPTY

    held = PresenceMachine(_calibration(), PresenceConfig(min_duration_s=3.0))
    assert held.update(_breath(0.0, 10.0), _still(0.0)).state == PresenceState.EMPTY
    assert held.update(_breath(3.0, 10.0), _still(3.0)).state == PresenceState.PRESENCE

    moving = held.update(_breath(4.0, 10.0), _still(4.0, moving=True, score=1.0))
    assert moving.state == PresenceState.MOTION
    assert moving.moving is True

    # Al frenar, la presencia tiene que volver a sostenerse.
    assert held.update(_breath(5.0, 10.0), _still(5.0)).state == PresenceState.EMPTY
    quiet = held.update(_breath(8.0, 10.0), _still(8.0))
    assert quiet.state == PresenceState.PRESENCE

    assert held.update(_breath(9.0, 0.0), _still(9.0)).state == PresenceState.PRESENCE
    assert held.update(_breath(12.0, 0.0), _still(12.0)).state == PresenceState.EMPTY
    assert set(PresenceState) == {
        PresenceState.EMPTY,
        PresenceState.PRESENCE,
        PresenceState.MOTION,
    }


def test_simulator_reports_still_presence_and_walk_motion():
    baseline = calibrate(SimulatedSource(SimConfig(seed=5, duration_s=25.0)), seconds=20.0)
    frames = SimulatedSource(
        SimConfig(
            seed=6,
            duration_s=70.0,
            events=(
                SimEvent("still", 10.0, 25.0),
                SimEvent("walk", 45.0, 8.0),
            ),
        )
    ).generate()
    _, _, presence = analyze_frames(frames, 100.0, baseline)

    def between(start: float, end: float) -> set[str]:
        return {sample.state for sample in presence if start <= sample.ts <= end}

    assert between(10.0, 12.0) <= {PresenceState.EMPTY}
    assert PresenceState.PRESENCE in between(28.0, 34.0)
    assert PresenceState.MOTION not in between(28.0, 34.0)
    assert PresenceState.MOTION in between(48.0, 58.0)
