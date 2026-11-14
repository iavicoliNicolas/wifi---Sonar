import pytest

from wifi_sonar.detect.occupancy import estimate_occupancy
from wifi_sonar.engine import Engine
from wifi_sonar.settings import Settings
from wifi_sonar.sources.rssi import RssiConfig, RssiSource
from wifi_sonar.sources.simulated import SimConfig, SimEvent, SimSignature, SimulatedSource


def _frames(seed: int = 1, **kwargs):
    config = SimConfig(seed=seed, duration_s=18.0, **kwargs)
    return SimulatedSource(config).generate()


def _count(frames, mode: str = "csi"):
    return estimate_occupancy(frames, 100.0, mode=mode)


def test_empty_room_is_zero_and_one_signature_is_one():
    empty = _count(_frames())
    assert empty.count == 0
    assert empty.label == "0"
    assert empty.low_confidence is False
    assert empty.confidence > 0.5

    still = _count(_frames(events=(SimEvent("still", 0.0, 18.0),)))
    walking = _count(_frames(events=(SimEvent("walk", 0.0, 18.0),)))
    assert still.label == "1"
    assert walking.label == "1"
    assert still.low_confidence is False
    assert walking.low_confidence is False


def test_two_distinguishable_signatures_cap_at_two_plus():
    breaths = (
        SimSignature("still", 0.0, 18.0, hz=0.18),
        SimSignature("still", 0.0, 18.0, hz=0.40, spatial_shift=1.5),
    )
    walks = (
        SimSignature("walk", 0.0, 18.0, hz=1.5),
        SimSignature("walk", 0.0, 18.0, hz=3.1, spatial_shift=1.2),
    )
    for seed in (1, 2, 7):
        quiet = _count(_frames(seed, signatures=breaths))
        moving = _count(_frames(seed, signatures=walks))
        assert quiet.label == "2+"
        assert moving.label == "2+"
        assert quiet.count == 2
        assert moving.count == 2
        assert quiet.confidence > 0.5
        assert moving.confidence > 0.5


def test_rssi_mode_keeps_confidence_low_and_names_nobody():
    estimate = _count(_frames(events=(SimEvent("walk", 0.0, 18.0),)), mode="rssi")
    assert estimate.low_confidence is True
    assert estimate.confidence <= 0.35
    assert "name" not in estimate.as_dict()
    assert estimate.label in ("0", "1", "2+")

    source = RssiSource(
        RssiConfig(
            devices=("telefono",),
            seed=3,
            duration_s=20.0,
            events=(SimEvent("still", 0.0, 20.0),),
        )
    )
    degraded = estimate_occupancy(source.generate(), source.sample_rate_hz, mode="rssi")
    assert degraded.low_confidence is True
    assert degraded.confidence <= 0.35


def test_unknown_signature_is_rejected():
    with pytest.raises(ValueError):
        SimSignature("enter", 0.0, 1.0, hz=1.0)


def test_status_and_websocket_publish_the_anonymous_count():
    engine = Engine(Settings(auto_start=False, source="file", seed=2))
    engine.calibrate(12)
    assert engine.status()["occupancy_label"] == "0"

    def ingest(frames) -> dict:
        fresh = Engine(Settings(auto_start=False, source="file", seed=2))
        fresh.calibrate(12)
        for frame in frames:
            fresh.ingest(frame)
        return fresh.status()

    empty = ingest(_frames(seed=4))
    assert empty["occupancy_label"] == "0"
    assert empty["occupancy_low_confidence"] is False

    one = ingest(_frames(seed=5, events=(SimEvent("still", 0.0, 18.0),)))
    assert one["occupancy_label"] == "1"
    assert one["nodes"][0]["occupancy_label"] == "1"
    assert "person" not in one

    two = ingest(
        _frames(
            seed=6,
            signatures=(
                SimSignature("walk", 0.0, 18.0, hz=1.5),
                SimSignature("walk", 0.0, 18.0, hz=3.1, spatial_shift=1.2),
            ),
        )
    )
    assert two["occupancy_label"] == "2+"
    assert two["occupancy_count"] == 2

    engine.update_config({"mode": "rssi"})
    for frame in _frames(seed=8, events=(SimEvent("walk", 0.0, 18.0),)):
        engine.ingest(frame)
    rssi = engine.status()
    assert rssi["mode"] == "rssi"
    assert rssi["occupancy_low_confidence"] is True
    assert rssi["occupancy_confidence"] <= 0.35
