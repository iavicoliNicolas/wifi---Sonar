"""Simulador determinista de CSI para desarrollar sin hardware."""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass

import numpy as np

from wifi_sonar.models import CSIFrame

EVENT_KINDS = ("enter", "walk", "still", "leave")


@dataclass(frozen=True, slots=True)
class SimEvent:
    """Intervalo en el que ocurre un evento.

    Los tiempos son segundos desde el inicio de la fuente. Si la fuente está en
    bucle, se interpretan dentro de cada período.
    """

    kind: str
    start_s: float
    duration_s: float

    def __post_init__(self) -> None:
        if self.kind not in EVENT_KINDS:
            raise ValueError(f"unknown event kind: {self.kind}")
        if self.duration_s < 0:
            raise ValueError("duration_s must be >= 0")


@dataclass(frozen=True, slots=True)
class SimConfig:
    seed: int = 0
    sample_rate_hz: float = 100.0
    n_subcarriers: int = 52
    duration_s: float | None = 30.0
    noise_sigma: float = 0.02
    drift_hz: float = 0.02
    drift_amp: float = 0.01
    walk_amp: float = 0.45
    walk_hz: float = 2.0
    breath_amp: float = 0.08
    breath_hz: float = 0.25
    burst_amp: float = 0.35
    burst_hz: float = 3.0
    null_subcarriers: tuple[int, ...] = (0,)
    node_id: str = "sim-0"
    rssi_base: float = -45.0
    events: tuple[SimEvent, ...] = ()
    loop: bool = False
    loop_period_s: float = 40.0

    def __post_init__(self) -> None:
        if self.sample_rate_hz <= 0:
            raise ValueError("sample_rate_hz must be positive")
        if self.n_subcarriers < 1:
            raise ValueError("n_subcarriers must be >= 1")
        if self.duration_s is not None and self.duration_s < 0:
            raise ValueError("duration_s must be >= 0")
        if self.loop and self.loop_period_s <= 0:
            raise ValueError("loop_period_s must be positive")


def demo_cycle(period_s: float = 40.0) -> tuple[SimEvent, ...]:
    """Un ciclo vacío → entrada → caminata → quietud → salida.

    Pensado para el panel en vivo. Los eventos caben en `period_s` de 40 s.
    """

    if period_s < 32:
        raise ValueError("demo cycle needs a period of at least 32 s")
    return (
        SimEvent("enter", 6.0, 1.5),
        SimEvent("walk", 8.0, 4.0),
        SimEvent("still", 13.0, 12.0),
        SimEvent("walk", 26.0, 3.0),
        SimEvent("leave", 30.0, 2.0),
    )


class SimulatedSource:
    """Genera CSI sintético: ruido, deriva lenta y eventos de ocupación.

    La misma semilla produce la misma secuencia. `duration_s=None` no termina:
    el servidor en vivo la usa junto con `loop=True`.
    """

    def __init__(self, config: SimConfig | None = None) -> None:
        self.config = config if config is not None else SimConfig()

    @property
    def sample_rate_hz(self) -> float:
        return self.config.sample_rate_hz

    def frames(self) -> Iterator[CSIFrame]:
        cfg = self.config
        if cfg.duration_s is None:
            yield from self._iter_forever()
            return
        yield from self.generate()

    def generate(self) -> list[CSIFrame]:
        cfg = self.config
        if cfg.duration_s is None:
            raise ValueError("generate() needs a finite duration_s")
        count = int(round(cfg.duration_s * cfg.sample_rate_hz))
        rng = np.random.default_rng(cfg.seed)
        return self._synthesize(0, count, rng)

    def _iter_forever(self) -> Iterator[CSIFrame]:
        cfg = self.config
        rng = np.random.default_rng(cfg.seed)
        chunk = max(1, int(round(cfg.sample_rate_hz)))
        index = 0
        while True:
            yield from self._synthesize(index, chunk, rng)
            index += chunk

    def _synthesize(
        self,
        start_index: int,
        count: int,
        rng: np.random.Generator,
    ) -> list[CSIFrame]:
        if count == 0:
            return []
        cfg = self.config
        fs = cfg.sample_rate_hz
        n_sc = cfg.n_subcarriers
        idx = np.arange(start_index, start_index + count)
        t = idx / fs
        base = 0.8 + 0.4 * np.sin(np.linspace(0, np.pi, n_sc))
        drift_phase = 0.3 * np.arange(n_sc)
        amps = np.broadcast_to(base, (count, n_sc)).copy()
        amps += cfg.drift_amp * np.sin(2 * np.pi * cfg.drift_hz * t[:, None] + drift_phase[None, :])
        amps += rng.normal(0.0, cfg.noise_sigma, size=(count, n_sc))
        clock = np.mod(t, cfg.loop_period_s) if cfg.loop else t
        _add_modulation(
            amps,
            t,
            clock,
            cfg.events,
            kind="still",
            amp=cfg.breath_amp,
            hz=cfg.breath_hz,
            spatial=np.linspace(0.2, 1.0, n_sc),
        )
        _add_modulation(
            amps,
            t,
            clock,
            cfg.events,
            kind="enter",
            amp=cfg.burst_amp,
            hz=cfg.burst_hz,
            spatial=1.0 + 0.5 * np.cos(np.linspace(0, 4 * np.pi, n_sc)),
        )
        _add_modulation(
            amps,
            t,
            clock,
            cfg.events,
            kind="leave",
            amp=cfg.burst_amp,
            hz=cfg.burst_hz,
            spatial=1.0 + 0.5 * np.cos(np.linspace(0, 3 * np.pi, n_sc)),
        )
        _add_modulation(
            amps,
            t,
            clock,
            cfg.events,
            kind="walk",
            amp=cfg.walk_amp,
            hz=cfg.walk_hz,
            spatial=1.0 + 0.3 * np.sin(np.linspace(0, 2 * np.pi, n_sc) + 0.4),
        )
        nulls = [i for i in cfg.null_subcarriers if 0 <= i < n_sc]
        if nulls:
            amps[:, nulls] = 0.0

        phases = rng.normal(0.0, 0.05, size=(count, n_sc)) + 0.002 * t[:, None]
        if nulls:
            phases[:, nulls] = 0.0
        rssi = np.full(count, cfg.rssi_base) + rng.normal(0.0, 0.4, size=count)
        _add_rssi(rssi, t, clock, cfg)

        amp_rows = amps.tolist()
        phase_rows = phases.tolist()
        node = cfg.node_id
        return [
            CSIFrame(
                timestamp=float(t[i]),
                rssi=float(rssi[i]),
                amplitudes=tuple(amp_rows[i]),
                phases=tuple(phase_rows[i]),
                node_id=node,
            )
            for i in range(count)
        ]


def _add_modulation(
    amps: np.ndarray,
    t: np.ndarray,
    clock: np.ndarray,
    events: tuple[SimEvent, ...],
    *,
    kind: str,
    amp: float,
    hz: float,
    spatial: np.ndarray,
) -> None:
    for event in events:
        if event.kind != kind or event.duration_s == 0:
            continue
        mask = (clock >= event.start_s) & (clock < event.start_s + event.duration_s)
        if not np.any(mask):
            continue
        wave = np.sin(2 * np.pi * hz * t[mask])
        amps[mask] += amp * wave[:, None] * spatial[None, :]


def _add_rssi(
    rssi: np.ndarray,
    t: np.ndarray,
    clock: np.ndarray,
    cfg: SimConfig,
) -> None:
    for event in cfg.events:
        if event.duration_s == 0:
            continue
        mask = (clock >= event.start_s) & (clock < event.start_s + event.duration_s)
        if not np.any(mask):
            continue
        if event.kind == "walk":
            rssi[mask] += 3.0 * np.sin(2 * np.pi * cfg.walk_hz * t[mask])
        elif event.kind == "still":
            rssi[mask] += 0.6 * np.sin(2 * np.pi * cfg.breath_hz * t[mask])
        elif event.kind in ("enter", "leave"):
            rssi[mask] += 2.0 * np.sin(2 * np.pi * cfg.burst_hz * t[mask])
