"""Motion detector with hysteresis and a minimum hold time.

A window counts as motion only when its motion-band energy clears the empty-room
threshold and is also stronger than the breathing band. Standing still leaks a
little energy into the motion band, but the breathing band is larger there, so
that case stays out of this detector (see D-010).
"""

from dataclasses import dataclass

import numpy as np

from wifi_sonar.detect.calibrate import Calibration
from wifi_sonar.pipeline.features import WindowFeatures


@dataclass(frozen=True)
class MotionSample:
    moving: bool
    score: float
    ts: float


class MotionDetector:
    def __init__(
        self,
        calibration: Calibration,
        *,
        hysteresis: float = 0.5,
        min_duration_s: float = 0.5,
    ) -> None:
        if not 0.0 <= hysteresis < 1.0:
            raise ValueError("hysteresis must be in [0, 1)")
        if min_duration_s < 0:
            raise ValueError("min_duration_s must be >= 0")
        mean = calibration.mean["motion_energy"]
        self.on_level = calibration.thresholds["motion_energy"]
        self.off_level = self.on_level - hysteresis * (self.on_level - mean)
        self.min_duration_s = min_duration_s
        self._scale = max(self.on_level * 8.0, 1e-9)
        self._above_since: float | None = None
        self._moving = False

    def update(self, features: WindowFeatures) -> MotionSample:
        energy = features.motion_energy
        score = float(np.clip((energy - self.off_level) / self._scale, 0.0, 1.0))
        louder_than_breathing = energy > features.breathing_energy
        if not self._moving:
            if energy >= self.on_level and louder_than_breathing:
                if self._above_since is None:
                    self._above_since = features.timestamp
                held = features.timestamp - self._above_since
                if held >= self.min_duration_s:
                    self._moving = True
            else:
                self._above_since = None
        elif energy <= self.off_level or energy <= features.breathing_energy:
            # Breathing louder than motion means someone still, not walking.
            self._moving = False
            self._above_since = None
        return MotionSample(moving=self._moving, score=score, ts=features.timestamp)
