"""Local presence and motion sensing from WiFi signal disturbance."""

__version__ = "0.0.1"

from wifi_sonar.sources.frame import CSIFrame
from wifi_sonar.sources.simulated import ScenarioEvent, SimulatedSource

__all__ = ["CSIFrame", "ScenarioEvent", "SimulatedSource", "__version__"]
