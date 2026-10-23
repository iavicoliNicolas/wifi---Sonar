"""Empty / presence / motion state machine.

Motion wins over presence. Presence requires the breathing band to stay above
its empty-room threshold for a longer hold than motion, so a brief bump does
not look like someone standing still.
"""

from dataclasses import dataclass
from typing import Literal

from wifi_sonar.detect.calibrate import Calibration
from wifi_sonar.detect.motion import MotionDetector, MotionSample
from wifi_sonar.pipeline.features import WindowFeatures

PresenceState = Literal["empty", "presence", "motion"]


@dataclass(frozen=True)
class PresenceSample:
    state: PresenceState
    ts: float
    motion: MotionSample


class PresenceDetector:
    def __init__(
        self,
        calibration: Calibration,
        *,
        hysteresis: float = 0.5,
        min_motion_s: float = 0.5,
        min_presence_s: float = 2.0,
    ) -> None:
        self.motion_detector = MotionDetector(
            calibration,
            hysteresis=hysteresis,
            min_duration_s=min_motion_s,
        )
        mean = calibration.mean["breathing_energy"]
        self.on_level = calibration.thresholds["breathing_energy"]
        self.off_level = self.on_level - hysteresis * (self.on_level - mean)
        self.min_presence_s = min_presence_s
        self._above_since: float | None = None
        self._present = False

    def update(self, features: WindowFeatures) -> PresenceSample:
        motion = self.motion_detector.update(features)
        if motion.moving:
            self._present = False
            self._above_since = None
            return PresenceSample(state="motion", ts=features.timestamp, motion=motion)
        energy = features.breathing_energy
        if not self._present:
            if energy >= self.on_level:
                if self._above_since is None:
                    self._above_since = features.timestamp
                if features.timestamp - self._above_since >= self.min_presence_s:
                    self._present = True
            else:
                self._above_since = None
        elif energy <= self.off_level:
            self._present = False
            self._above_since = None
        state: PresenceState = "presence" if self._present else "empty"
        return PresenceSample(state=state, ts=features.timestamp, motion=motion)
