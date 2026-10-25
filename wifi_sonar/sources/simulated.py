"""Deterministic CSI simulator for development without hardware."""

from collections.abc import Iterator, Sequence
from dataclasses import dataclass
from typing import Literal

import numpy as np

from wifi_sonar.sources.frame import CSIFrame

EventKind = Literal["enter", "walk", "still", "leave"]

# Modulation (Hz, amplitude) added on top of empty-room noise.
# Walk is a fast, large disturbance. Still is a slow breathing-like wave.
# Enter and leave are short transitions between those regimes.
_EVENT_TONE: dict[EventKind, tuple[float, float]] = {
    "enter": (1.5, 0.18),
    "walk": (2.0, 0.55),
    "still": (0.25, 0.12),
    "leave": (1.0, 0.16),
}

_EMPTY_NOISE = 0.012
_DRIFT_HZ = 0.02
_DRIFT_AMP = 0.01


@dataclass(frozen=True)
class ScenarioEvent:
    """A scripted disturbance. Times are seconds from the start of the trace."""

    kind: EventKind
    start_s: float
    duration_s: float

    def __post_init__(self) -> None:
        if self.kind not in _EVENT_TONE:
            raise ValueError(f"unknown event kind: {self.kind}")
        if self.duration_s <= 0:
            raise ValueError("duration_s must be positive")
        if self.start_s < 0:
            raise ValueError("start_s must be >= 0")


class SimulatedSource:
    """~52-subcarrier CSI trace. The same seed and events always replay identically.

    Empty stretches are low-variance noise plus a slow drift. Each event adds a
    tone whose amplitude is large for walking and small for standing still, so
    downstream variance and band-energy features can tell them apart.
    """

    def __init__(
        self,
        *,
        seed: int,
        duration_s: float,
        sample_rate_hz: float = 50.0,
        n_subcarriers: int = 52,
        events: Sequence[ScenarioEvent] = (),
        node_id: str = "sim-0",
    ) -> None:
        if duration_s <= 0:
            raise ValueError("duration_s must be positive")
        if sample_rate_hz <= 0:
            raise ValueError("sample_rate_hz must be positive")
        if n_subcarriers < 1:
            raise ValueError("n_subcarriers must be >= 1")
        self.seed = seed
        self.duration_s = duration_s
        self.sample_rate_hz = sample_rate_hz
        self.n_subcarriers = n_subcarriers
        self.events = tuple(events)
        self.node_id = node_id
        self._frames: tuple[CSIFrame, ...] | None = None

    def __iter__(self) -> Iterator[CSIFrame]:
        yield from self.frames()

    def frames(self) -> tuple[CSIFrame, ...]:
        if self._frames is None:
            self._frames = tuple(self._generate())
        return self._frames

    def _generate(self) -> Iterator[CSIFrame]:
        rng = np.random.default_rng(self.seed)
        n = int(round(self.duration_s * self.sample_rate_hz))
        fs = self.sample_rate_hz
        times = np.arange(n, dtype=np.float64) / fs
        sub_phase = rng.uniform(0.0, 2.0 * np.pi, size=self.n_subcarriers)
        sub_gain = 0.85 + 0.3 * rng.random(self.n_subcarriers)
        noise = rng.normal(0.0, _EMPTY_NOISE, size=(n, self.n_subcarriers))
        phase_noise = rng.normal(0.0, 0.02, size=(n, self.n_subcarriers))

        drift = _DRIFT_AMP * np.sin(2.0 * np.pi * _DRIFT_HZ * times)
        amps = sub_gain * (1.0 + drift[:, None]) + noise
        phases = sub_phase + 0.05 * drift[:, None] + phase_noise

        for event in self.events:
            start = int(round(event.start_s * fs))
            stop = min(n, int(round((event.start_s + event.duration_s) * fs)))
            if stop <= start:
                continue
            freq, amp = _EVENT_TONE[event.kind]
            local_t = times[start:stop]
            # Per-subcarrier phase keeps the disturbance from being a single tone
            # copied onto every carrier, which is closer to a body moving in a room.
            tone = np.sin(2.0 * np.pi * freq * local_t[:, None] + sub_phase)
            amps[start:stop] += amp * tone
            phases[start:stop] += 0.35 * amp * tone

        # RSSI tracks the mean power of the carriers, in dB, with an arbitrary offset.
        power = np.mean(np.square(amps), axis=1)
        rssi = -50.0 + 10.0 * np.log10(np.maximum(power, 1e-9))

        for i in range(n):
            yield CSIFrame(
                timestamp=float(times[i]),
                rssi=float(rssi[i]),
                amplitudes=amps[i].copy(),
                phases=phases[i].copy(),
                node_id=self.node_id,
            )


def amplitude_variance(frames: Sequence[CSIFrame]) -> float:
    """Mean temporal variance across subcarriers. Used to check scripted events."""
    if not frames:
        return 0.0
    matrix = np.stack([frame.amplitudes for frame in frames])
    return float(np.mean(np.var(matrix, axis=0)))
