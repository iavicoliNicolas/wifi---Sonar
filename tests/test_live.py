from wifi_sonar.live import demo_stream
from wifi_sonar.runtime import SonarConfig, SonarState


def _zone_at(snapshots: list[dict[str, object]], ts: float) -> dict[str, str]:
    chosen = min(snapshots, key=lambda item: abs(float(item["ts"]) - ts))
    zones = chosen["zones"]
    assert isinstance(zones, list)
    return {str(zone["name"]): str(zone["state"]) for zone in zones}


def test_demo_walks_in_living_and_leaves_the_hall_empty() -> None:
    state = SonarState(config=SonarConfig(n_subcarriers=8))
    state.calibrate(8)
    snapshots = demo_stream(state, seed=3, n_subcarriers=8)
    early = _zone_at(snapshots, 2.0)
    assert early == {"living": "empty", "pasillo": "empty"}
    walking = _zone_at(snapshots, 8.0)
    assert walking == {"living": "motion", "pasillo": "empty"}
    assert state.capture_from_recent is False
