from wifi_sonar.detect.calibrate import calibrate
from wifi_sonar.detect.observe import observe
from wifi_sonar.detect.presence import PresenceDetector
from wifi_sonar.sources.simulated import ScenarioEvent, SimulatedSource


def test_presence_state_machine() -> None:
    calibration = calibrate(SimulatedSource(seed=1, duration_s=20.0), seconds=20.0, k=6.0)
    empty = observe(SimulatedSource(seed=4, duration_s=12.0))
    still = observe(
        SimulatedSource(
            seed=4,
            duration_s=18.0,
            events=(ScenarioEvent("still", 0.0, 18.0),),
        )
    )
    walk = observe(
        SimulatedSource(
            seed=4,
            duration_s=8.0,
            events=(ScenarioEvent("walk", 0.0, 8.0),),
        )
    )

    def states(features) -> list[str]:
        detector = PresenceDetector(calibration)
        return [detector.update(item).state for item in features]

    empty_states = states(empty)
    still_states = states(still)
    walk_states = states(walk)
    assert "motion" not in empty_states
    assert empty_states[-1] == "empty"
    assert "motion" not in still_states
    assert "presence" in still_states
    assert still_states[-1] == "presence"
    assert "motion" in walk_states
    assert walk_states[-1] == "motion"
