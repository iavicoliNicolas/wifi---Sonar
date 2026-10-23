"""Calibration and detectors. They see features, not raw hardware."""

from wifi_sonar.detect.calibrate import Calibration, calibrate, load_calibration, save_calibration
from wifi_sonar.detect.motion import MotionDetector, MotionSample
from wifi_sonar.detect.observe import observe
from wifi_sonar.detect.presence import PresenceDetector, PresenceSample

__all__ = [
    "Calibration",
    "MotionDetector",
    "MotionSample",
    "PresenceDetector",
    "PresenceSample",
    "calibrate",
    "load_calibration",
    "observe",
    "save_calibration",
]
