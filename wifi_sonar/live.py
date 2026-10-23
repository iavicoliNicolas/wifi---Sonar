"""Background simulator that publishes snapshots for the local panel."""

import threading
import time

from fastapi import FastAPI

from wifi_sonar.api.stream import follow
from wifi_sonar.detect.rssi import detect_rssi, simulated_rssi
from wifi_sonar.detect.zones import zone_states
from wifi_sonar.sources.simulated import ScenarioEvent, SimulatedSource


def scenario(seed: int, n_subcarriers: int) -> SimulatedSource:
    return SimulatedSource(
        seed=seed,
        duration_s=24.0,
        n_subcarriers=n_subcarriers,
        events=(
            ScenarioEvent("walk", 6.0, 5.0),
            ScenarioEvent("still", 14.0, 8.0),
        ),
    )


def live_loop(app: FastAPI, stop: threading.Event, *, pace_s: float = 0.1) -> None:
    state = app.state.sonar
    if state.calibration is None:
        state.calibrate(8.0)
    seed = 1
    while not stop.is_set():
        if state.paused:
            stop.wait(0.2)
            continue
        token = state.config.model_dump_json()
        seed += 1
        if state.config.mode == "rssi":
            stream = _rssi_snapshots(state.config.rssi_devices, seed)
        else:
            source = scenario(seed, state.config.n_subcarriers)
            stream = follow(state, source, hz=10.0, stored_clock=time.time)
        for snapshot in stream:
            if stop.is_set() or state.paused or state.config.model_dump_json() != token:
                break
            snapshot["zones"] = _zones(str(snapshot["state"]), state.config)
            app.state.hub.publish(snapshot)
            if pace_s > 0:
                stop.wait(pace_s)


def _rssi_snapshots(devices: list[str], seed: int) -> list[dict[str, object]]:
    device_id = devices[0] if devices else "ap-propio"
    # A scripted swing stands in for someone walking. The label is the operator's.
    points = simulated_rssi(seed, 24.0, device_id=device_id, swing=True)
    return detect_rssi(points)


def _zones(sample_state: str, config: object) -> list[dict[str, str]]:
    zones = getattr(config, "zones", ())
    mode = getattr(config, "fusion", "or")
    if zones:
        mapping = {"sim-0": sample_state}
        return zone_states(mapping, [(zone.name, zone.node_ids) for zone in zones], mode)
    return [{"name": "esta habitación", "state": sample_state}]


def start_live(app: FastAPI) -> threading.Event:
    stop = threading.Event()
    thread = threading.Thread(
        target=live_loop,
        args=(app, stop),
        name="wifi-sonar-live",
        daemon=True,
    )
    thread.start()
    return stop
