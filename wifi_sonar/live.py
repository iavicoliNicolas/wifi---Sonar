"""Background simulator that publishes snapshots for the local panel."""

import threading

from fastapi import FastAPI

from wifi_sonar.api.stream import follow
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
        source = scenario(seed, state.config.n_subcarriers)
        seed += 1
        for snapshot in follow(state, source, hz=10.0):
            if stop.is_set() or state.paused or state.config.model_dump_json() != token:
                break
            app.state.hub.publish(snapshot)
            if pace_s > 0:
                stop.wait(pace_s)


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
