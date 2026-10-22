"""RSSI de dispositivos que la persona ya nombró. No escanea la red."""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass, replace

import numpy as np

from wifi_sonar.models import CSIFrame
from wifi_sonar.sources.simulated import SimEvent, demo_cycle


@dataclass(frozen=True, slots=True)
class RssiConfig:
    """`devices` es una lista blanca. Un nombre vacío no significa 'descubrir vecinos'."""

    devices: tuple[str, ...]
    seed: int = 0
    sample_rate_hz: float = 20.0
    duration_s: float | None = 30.0
    noise_sigma: float = 0.35
    base_rssi: float = -48.0
    events: tuple[SimEvent, ...] = ()

    def __post_init__(self) -> None:
        names = tuple(name.strip() for name in self.devices if name.strip())
        if not names:
            raise ValueError("rssi mode needs your own device names; it does not scan the LAN")
        if names != self.devices:
            object.__setattr__(self, "devices", names)
        if self.sample_rate_hz <= 0:
            raise ValueError("sample_rate_hz must be positive")
        if self.duration_s is not None and self.duration_s < 0:
            raise ValueError("duration_s must be >= 0")


class RssiSource:
    """Un frame por dispositivo conocido, con la RSSI como única subportadora.

    Sirve para el modo degradado. La variación es mucho más gruesa que el CSI
    y el panel tiene que decirlo. No hay barrido de redes ni de vecinos.
    """

    def __init__(self, config: RssiConfig) -> None:
        self.config = config

    @property
    def sample_rate_hz(self) -> float:
        return self.config.sample_rate_hz

    def frames(self) -> Iterator[CSIFrame]:
        cfg = self.config
        if cfg.duration_s is None:
            yield from self._iter_forever()
            return
        yield from self.generate()

    def _iter_forever(self) -> Iterator[CSIFrame]:
        period = 40.0
        offset = 0.0
        events = self.config.events or demo_cycle()
        while True:
            chunk = RssiSource(replace(self.config, duration_s=period, events=events))
            for frame in chunk.generate():
                yield replace(frame, timestamp=frame.timestamp + offset)
            offset += period

    def generate(self) -> list[CSIFrame]:
        cfg = self.config
        if cfg.duration_s is None:
            raise ValueError("generate() needs a finite duration_s")
        count = int(round(cfg.duration_s * cfg.sample_rate_hz))
        rng = np.random.default_rng(cfg.seed)
        times = np.arange(count) / cfg.sample_rate_hz
        frames: list[CSIFrame] = []
        for device_index, name in enumerate(cfg.devices):
            rssi = np.full(count, cfg.base_rssi) + rng.normal(0.0, cfg.noise_sigma, size=count)
            rssi += 0.15 * device_index
            _apply_events(rssi, times, cfg.events)
            for index in range(count):
                value = float(rssi[index])
                frames.append(
                    CSIFrame(
                        timestamp=float(times[index]),
                        rssi=value,
                        amplitudes=(value,),
                        node_id=name,
                    )
                )
        frames.sort(key=lambda frame: (frame.timestamp, frame.node_id))
        return frames


def _apply_events(rssi: np.ndarray, times: np.ndarray, events: tuple[SimEvent, ...]) -> None:
    for event in events:
        if event.duration_s == 0:
            continue
        mask = (times >= event.start_s) & (times < event.start_s + event.duration_s)
        if not np.any(mask):
            continue
        if event.kind == "walk":
            rssi[mask] += 8.0 * np.sin(2 * np.pi * 2.0 * times[mask])
        elif event.kind == "still":
            rssi[mask] += 2.2 * np.sin(2 * np.pi * 0.25 * times[mask])
        elif event.kind in ("enter", "leave"):
            rssi[mask] += 5.0 * np.sin(2 * np.pi * 1.5 * times[mask])
