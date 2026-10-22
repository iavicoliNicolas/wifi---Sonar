import numpy as np
import pytest

from wifi_sonar.sources.base import CSISource, read_frames
from wifi_sonar.sources.replay import ReplaySource, write_recording
from wifi_sonar.sources.simulated import SimConfig, SimEvent, SimulatedSource


def _assert_same_frames(left, right):
    assert len(left) == len(right)
    for original, replayed in zip(left, right, strict=True):
        assert replayed.timestamp == pytest.approx(original.timestamp)
        assert replayed.rssi == pytest.approx(original.rssi)
        assert replayed.node_id == original.node_id
        assert np.allclose(replayed.amplitudes, original.amplitudes)
        assert np.allclose(replayed.phases, original.phases)


def test_simulator_and_replay_share_the_pipeline(tmp_path):
    config = SimConfig(
        seed=4,
        duration_s=0.5,
        events=(SimEvent("walk", 0.2, 0.2),),
    )
    simulated = SimulatedSource(config)
    assert isinstance(simulated, CSISource)
    original = read_frames(simulated)

    jsonl = tmp_path / "session.jsonl"
    csv_path = tmp_path / "session.csv"
    write_recording(jsonl, original)
    write_recording(csv_path, original)

    from_jsonl = ReplaySource(jsonl, speed=0)
    from_csv = ReplaySource(csv_path, speed=0)
    assert isinstance(from_jsonl, CSISource)
    assert from_jsonl.sample_rate_hz == pytest.approx(100.0)

    _assert_same_frames(original, read_frames(from_jsonl))
    _assert_same_frames(original, read_frames(from_csv))
    _assert_same_frames(read_frames(from_jsonl), read_frames(from_csv))


def test_speed_controls_the_sleeper(tmp_path):
    original = SimulatedSource(SimConfig(seed=1, duration_s=0.05)).generate()
    path = tmp_path / "short.jsonl"
    write_recording(path, original)
    delays: list[float] = []

    fast = ReplaySource(path, speed=0, sleeper=delays.append)
    assert len(read_frames(fast)) == len(original)
    assert delays == []

    realtime = ReplaySource(path, speed=2, sleeper=delays.append)
    assert len(read_frames(realtime)) == len(original)
    assert delays
    assert delays[0] == pytest.approx(0.01 / 2)


def test_invalid_jsonl_line_is_rejected(tmp_path):
    path = tmp_path / "broken.jsonl"
    path.write_text("{not json}\n", encoding="utf-8")
    with pytest.raises(ValueError, match="invalid CSI record"):
        ReplaySource(path)
