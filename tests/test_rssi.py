from fastapi.testclient import TestClient
from wifi_sonar.api import create_app
from wifi_sonar.detect.rssi import detect_rssi, simulated_rssi
from wifi_sonar.runtime import SonarConfig, SonarState


def test_rssi_motion_needs_a_swing_and_never_claims_presence() -> None:
    quiet = detect_rssi(simulated_rssi(1, 20.0, device_id="ap-living", swing=False))
    moving = detect_rssi(simulated_rssi(1, 12.0, device_id="ap-living", swing=True))
    assert quiet[-1]["state"] == "empty"
    assert all(item["state"] != "presence" for item in quiet + moving)
    assert any(item["state"] == "motion" for item in moving)
    try:
        simulated_rssi(1, 4.0, device_id="*")
    except ValueError:
        pass
    else:
        raise AssertionError("a wildcard device id must be rejected")


def test_rssi_mode_is_rejected_for_a_scan_label() -> None:
    client = TestClient(create_app(SonarState(config=SonarConfig(n_subcarriers=8))))
    body = client.get("/config").json()
    body["mode"] = "rssi"
    body["rssi_devices"] = ["*"]
    assert client.put("/config", json=body).status_code == 422
    body["rssi_devices"] = ["ap-living"]
    stored = client.put("/config", json=body)
    assert stored.status_code == 200
    assert stored.json()["mode"] == "rssi"
    assert stored.json()["rssi_devices"] == ["ap-living"]
