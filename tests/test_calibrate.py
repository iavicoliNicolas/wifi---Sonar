import pytest

from wifi_sonar.detect.calibrate import baseline_quality, calibrate, load_calibration
from wifi_sonar.engine import Engine
from wifi_sonar.settings import Settings
from wifi_sonar.sources.simulated import SimConfig, SimEvent, SimulatedSource


def test_calibrate_persists_thresholds_from_an_empty_room(tmp_path):
    source = SimulatedSource(SimConfig(seed=11, duration_s=22.0))
    destination = tmp_path / "baseline.json"
    calibration = calibrate(source, seconds=20.0, k=4.0, path=destination)

    assert destination.is_file()
    loaded = load_calibration(destination)
    assert loaded.created_at == calibration.created_at
    assert loaded.k == 4.0
    assert loaded.sample_rate_hz == pytest.approx(100.0)
    for name in ("variance", "mad", "motion_energy", "breath_energy"):
        assert loaded.mean[name] == pytest.approx(calibration.mean[name])
        assert loaded.std[name] == pytest.approx(calibration.std[name])
        assert loaded.thresholds[name] == pytest.approx(
            calibration.mean[name] + 4.0 * calibration.std[name]
        )
        assert loaded.thresholds[name] >= loaded.mean[name]
    assert loaded.mean["motion_energy"] > 0


def test_an_attached_quiet_source_changes_the_empty_room_baseline():
    settings = Settings(auto_start=False, seed=0)
    reference = Engine(settings).calibrate(12)
    attached = Engine(settings).calibrate(
        12,
        source=SimulatedSource(SimConfig(seed=4, duration_s=13.0)),
    )
    assert attached.mean["motion_energy"] != pytest.approx(reference.mean["motion_energy"])
    assert baseline_quality(attached) == "estable"


def test_a_recent_walk_is_not_a_good_baseline():
    settings = Settings(auto_start=False, seed=0)
    reference = Engine(settings).calibrate(12)
    engine = Engine(settings)
    engine.capture_from_recent = True
    walk = SimulatedSource(
        SimConfig(seed=1, duration_s=14.0, events=(SimEvent("walk", 0.0, 14.0),))
    )
    for frame in walk.generate():
        engine.remember(frame)
    noisy = engine.calibrate(12)
    assert baseline_quality(noisy) == "ruidosa"
    assert noisy.mean["motion_energy"] != pytest.approx(reference.mean["motion_energy"])

    engine.recent.clear()
    fallback = engine.calibrate(12)
    assert fallback.mean["motion_energy"] == pytest.approx(reference.mean["motion_energy"])
    assert engine.capture_from_recent is True
    assert Engine(settings).capture_from_recent is False


def test_short_capture_is_rejected():
    source = SimulatedSource(SimConfig(seed=1, duration_s=5.0))
    with pytest.raises(ValueError):
        calibrate(source, seconds=5.0)
