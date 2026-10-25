from wifi_sonar.runtime import SonarConfig, SonarState
from wifi_sonar.sources.simulated import ScenarioEvent, SimulatedSource
from wifi_sonar.storage import Store


def test_migration_persists_events_calibration_and_config(tmp_path) -> None:
    path = tmp_path / "sonar.sqlite3"
    store = Store(path)
    assert store._conn.execute("SELECT value FROM meta WHERE key = 'schema'").fetchone()[0] == "1"
    state = SonarState(config=SonarConfig(n_subcarriers=8), store=store)
    state.replace_config(SonarConfig(n_subcarriers=8, hysteresis=0.25, k=5.0))
    state.calibrate(8)
    state.run(
        SimulatedSource(
            seed=3,
            duration_s=6.0,
            n_subcarriers=8,
            events=(ScenarioEvent("walk", 0.0, 6.0),),
        )
    )
    store.close()

    reopened = Store(path)
    restored = SonarState(store=reopened)
    assert restored.config.hysteresis == 0.25
    assert restored.config.k == 5.0
    assert restored.calibration is not None
    assert restored.history[-1]["state"] == "motion"
    reopened.close()


def test_purge_drops_events_older_than_retention(tmp_path) -> None:
    store = Store(tmp_path / "old.sqlite3")
    store.add_event(0.0, "empty", 0.0)
    store.add_event(10.0, "motion", 1.0)
    store.add_event(500.0, "presence", 0.4)
    removed = store.purge(retention_s=100, now=500.0)
    assert removed == 2
    remaining = store.events()
    assert len(remaining) == 1
    assert remaining[0]["state"] == "presence"
    store.close()
