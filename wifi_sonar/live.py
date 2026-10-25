"""Background simulator that publishes snapshots for the local panel."""

import threading
import time
from collections.abc import Callable

from fastapi import FastAPI

from wifi_sonar.api.stream import follow, state_at, trace_states
from wifi_sonar.detect.rssi import detect_rssi, simulated_rssi
from wifi_sonar.detect.zones import fuse_states, zone_states
from wifi_sonar.runtime import SonarState
from wifi_sonar.sources.simulated import ScenarioEvent, SimulatedSource

_WALK = (ScenarioEvent("walk", 6.0, 5.0), ScenarioEvent("still", 14.0, 8.0))


def scenario(seed: int, n_subcarriers: int, *, node_id: str = "living") -> SimulatedSource:
    return SimulatedSource(
        seed=seed,
        duration_s=24.0,
        n_subcarriers=n_subcarriers,
        events=_WALK,
        node_id=node_id,
    )


def demo_stream(
    state: SonarState,
    seed: int,
    n_subcarriers: int,
    *,
    stored_clock: Callable[[], float] | None = None,
) -> list[dict[str, object]]:
    """Living plays the 24 s scene. The hall stays empty. Both zones go on each snapshot."""
    living = scenario(seed, n_subcarriers, node_id="living")
    hall = SimulatedSource(
        seed=seed,
        duration_s=24.0,
        n_subcarriers=n_subcarriers,
        node_id="pasillo",
    )
    hall_states = trace_states(state, hall)
    snapshots = follow(state, living, hz=10.0, stored_clock=stored_clock)
    for snapshot in snapshots:
        living_state = str(snapshot["state"])
        hall_state = state_at(hall_states, float(snapshot["ts"]))
        snapshot["zones"] = _demo_zones(
            {"living": living_state, "pasillo": hall_state},
            state.config,
        )
    return snapshots


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
            stream = rssi_snapshots(state.config.rssi_devices, seed)
        else:
            stream = demo_stream(
                state,
                seed,
                state.config.n_subcarriers,
                stored_clock=time.time,
            )
        for snapshot in stream:
            if stop.is_set() or state.paused or state.config.model_dump_json() != token:
                break
            if "zones" not in snapshot:
                snapshot["zones"] = _zones(str(snapshot["state"]), state.config)
            app.state.hub.publish(snapshot)
            if pace_s > 0:
                stop.wait(pace_s)


def rssi_snapshots(devices: list[str], seed: int) -> list[dict[str, object]]:
    """One row per name the operator typed. Only the first name swings in the demo."""
    labels = [item for item in devices if item] or ["ap-propio"]
    series = [
        detect_rssi(simulated_rssi(seed, 24.0, device_id=label, swing=index == 0))
        for index, label in enumerate(labels)
    ]
    merged: list[dict[str, object]] = []
    count = min(len(rows) for rows in series)
    for index in range(count):
        states = [str(rows[index]["state"]) for rows in series]
        scores = [float(rows[index]["score"]) for rows in series]
        zones = [{"name": label, "state": states[pos]} for pos, label in enumerate(labels)]
        merged.append(
            {
                "ts": series[0][index]["ts"],
                "state": fuse_states(states, "or"),
                "score": max(scores) if scores else 0.0,
                "mode": "rssi",
                "zones": zones,
            }
        )
    return merged


def _demo_zones(node_states: dict[str, str], config: object) -> list[dict[str, str]]:
    zones = getattr(config, "zones", ())
    mode = getattr(config, "fusion", "or")
    if zones:
        return zone_states(node_states, [(zone.name, zone.node_ids) for zone in zones], mode)
    return [
        {"name": "living", "state": node_states.get("living", "empty")},
        {"name": "pasillo", "state": node_states.get("pasillo", "empty")},
    ]


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
