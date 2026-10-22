from wifi_sonar.engine import Engine
from wifi_sonar.settings import Settings
from wifi_sonar.sources.simulated import SimConfig, SimEvent, SimulatedSource


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
