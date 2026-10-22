from datetime import UTC, datetime, timedelta

from wifi_sonar.storage.sqlite import SqliteStore


def _event(state: str, recorded_at: str) -> dict[str, object]:
    return {
        "ts": 1.0,
        "state": state,
        "score": 0.5,
        "node_id": "sim-0",
        "zone": "living",
        "recorded_at": recorded_at,
    }


def test_migration_roundtrip_and_retention(tmp_path):
    path = tmp_path / "nested" / "sonar.sqlite"
    store = SqliteStore(path, retention_days=30)
    store.migrate()
    store.save_config({"sensitivity": 1.2, "paused": False})
    store.save_calibration({"created_at": "2026-10-22T00:00:00+00:00", "k": 8})

    old = (datetime.now(UTC) - timedelta(days=40)).isoformat()
    recent = datetime.now(UTC).isoformat()
    store.add_event(_event("movimiento", old))
    assert store.list_events() == []
    store.add_event(_event("presencia", recent))

    reopened = SqliteStore(path, retention_days=30)
    assert reopened.load_config()["sensitivity"] == 1.2
    assert reopened.load_calibration()["k"] == 8
    events = reopened.list_events()
    assert len(events) == 1
    assert events[0]["state"] == "presencia"
    assert events[0]["zone"] == "living"

    removed = reopened.purge(retention_days=0, now=datetime.now(UTC) + timedelta(days=1))
    assert removed == 1
    assert reopened.list_events() == []
