import math
from pathlib import Path

import numpy as np
from wifi_sonar.pipeline import collect
from wifi_sonar.sources.replay import ReplaySource, dump_csv, dump_jsonl
from wifi_sonar.sources.simulated import ScenarioEvent, SimulatedSource


def _sample():
    return SimulatedSource(
        seed=4,
        duration_s=0.4,
        sample_rate_hz=25.0,
        events=(ScenarioEvent("walk", 0.1, 0.2),),
        node_id="living",
    ).frames()


def _assert_same(left, right) -> None:
    assert len(left) == len(right)
    for a, b in zip(left, right, strict=True):
        assert a.timestamp == b.timestamp
        assert a.rssi == b.rssi
        assert a.node_id == b.node_id
        assert np.allclose(a.amplitudes, b.amplitudes)
        assert a.phases is not None and b.phases is not None
        assert np.allclose(a.phases, b.phases)


def test_jsonl_replay_matches_simulator_through_the_same_pipeline(tmp_path) -> None:
    original = _sample()
    path = tmp_path / "trace.jsonl"
    dump_jsonl(original, path)
    replayed = collect(ReplaySource(path, speed=0))
    direct = collect(
        SimulatedSource(
            seed=4,
            duration_s=0.4,
            sample_rate_hz=25.0,
            events=(ScenarioEvent("walk", 0.1, 0.2),),
            node_id="living",
        )
    )
    _assert_same(replayed, direct)
    _assert_same(replayed, original)


def test_csv_replay_matches_jsonl(tmp_path) -> None:
    original = _sample()
    csv_path = tmp_path / "trace.csv"
    jsonl_path = tmp_path / "trace.jsonl"
    dump_csv(original, csv_path)
    dump_jsonl(original, jsonl_path)
    _assert_same(collect(ReplaySource(csv_path)), collect(ReplaySource(jsonl_path)))


def test_accelerated_replay_sleeps_for_a_fraction_of_the_gap(tmp_path: Path) -> None:
    original = _sample()
    sleeps: list[float] = []
    now = {"t": 100.0}

    def clock() -> float:
        return now["t"]

    def sleep(seconds: float) -> None:
        sleeps.append(seconds)
        now["t"] += seconds

    path = tmp_path / "paced.jsonl"
    dump_jsonl(original, path)
    frames = collect(ReplaySource(path, speed=4.0, sleep=sleep, clock=clock))
    assert len(frames) == len(original)
    gap = frames[1].timestamp - frames[0].timestamp
    assert math.isclose(sleeps[0], gap / 4.0, rel_tol=1e-9)
