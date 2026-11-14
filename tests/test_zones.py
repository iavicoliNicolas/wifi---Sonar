import pytest

from wifi_sonar.engine import Engine, NodeRuntime, build_source
from wifi_sonar.settings import Settings
from wifi_sonar.sources.simulated import (
    HomeDemoSource,
    SimConfig,
    SimEvent,
    SimulatedSource,
    home_demo_frames,
)


def test_simulated_nodes_report_a_state_per_zone_and_fuse_with_or():
    engine = Engine(Settings(auto_start=False, source="file", seed=2))
    engine.calibrate(12)
    engine.update_config(
        {
            "fusion": "or",
            "zones": {"living": "living", "pasillo": "pasillo"},
        }
    )
    walk = SimulatedSource(
        SimConfig(
            seed=3,
            duration_s=16.0,
            node_id="living",
            events=(SimEvent("walk", 0.0, 16.0),),
        )
    )
    quiet = SimulatedSource(
        SimConfig(
            seed=4,
            duration_s=16.0,
            node_id="pasillo",
            events=(SimEvent("still", 0.0, 16.0),),
        )
    )
    for moving, still in zip(walk.generate(), quiet.generate(), strict=True):
        engine.ingest(moving)
        engine.ingest(still)

    status = engine.status()
    by_zone = {row["zone"]: row["state"] for row in status["nodes"]}
    assert by_zone["living"] == "movimiento"
    assert "pasillo" in by_zone
    assert status["state"] == "movimiento"

    engine.update_config({"fusion": "vote"})
    voted = engine.status()
    assert {row["zone"] for row in voted["nodes"]} == {"living", "pasillo"}


def test_panel_demo_walks_in_living_and_leaves_the_hall_empty():
    engine = Engine(Settings(auto_start=False, seed=3, source="sim"))
    assert isinstance(build_source(engine.settings), HomeDemoSource)
    assert engine.capture_from_recent is False
    engine.calibrate(12)
    empty = engine.calibration.mean["motion_energy"]
    frames = [frame for frame in home_demo_frames(3, 16.0) if frame.timestamp <= 14.0]
    for frame in frames:
        engine.ingest(frame)
    by_node = {row["node_id"]: row["state"] for row in engine.status()["nodes"]}
    assert by_node == {"living": "movimiento", "pasillo": "vacío"}
    assert engine.status()["state"] == "movimiento"
    engine.recent.clear()
    again = engine.calibrate(12)
    assert again.mean["motion_energy"] == pytest.approx(empty)


def test_renaming_a_zone_does_not_reset_the_detector():
    engine = Engine(Settings(auto_start=False, source="file"))
    node = engine.nodes.setdefault("sim-0", NodeRuntime())
    node.state = "movimiento"
    node.motion = object()
    engine.update_config({"zones": {"sim-0": "living"}})
    assert engine.nodes["sim-0"].motion is not None
    assert engine.nodes["sim-0"].state == "movimiento"
    assert engine.status()["nodes"][0]["zone"] == "living"
    engine.update_config({"sensitivity": 1.2})
    assert engine.nodes["sim-0"].motion is None
