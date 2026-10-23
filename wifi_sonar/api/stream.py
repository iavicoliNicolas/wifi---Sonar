"""WebSocket fan-out. A slow client loses old snapshots instead of blocking the sensor."""

import asyncio
from collections.abc import Callable, Iterator

import numpy as np

from wifi_sonar.detect.presence import PresenceDetector
from wifi_sonar.pipeline.features import extract_features
from wifi_sonar.pipeline.preprocess import preprocess
from wifi_sonar.runtime import SonarState
from wifi_sonar.sources.base import CSISource
from wifi_sonar.sources.frame import CSIFrame


class FrameHub:
    def __init__(self, maxlen: int = 8) -> None:
        if maxlen < 1:
            raise ValueError("maxlen must be >= 1")
        self.maxlen = maxlen
        self._subscribers: list[asyncio.Queue[dict[str, object]]] = []

    def subscribe(self) -> asyncio.Queue[dict[str, object]]:
        queue: asyncio.Queue[dict[str, object]] = asyncio.Queue(maxsize=self.maxlen)
        self._subscribers.append(queue)
        return queue

    def unsubscribe(self, queue: asyncio.Queue[dict[str, object]]) -> None:
        if queue in self._subscribers:
            self._subscribers.remove(queue)

    def publish(self, payload: dict[str, object]) -> None:
        for queue in list(self._subscribers):
            _offer(queue, payload)


def _offer(queue: asyncio.Queue[dict[str, object]], payload: dict[str, object]) -> None:
    if queue.full():
        try:
            queue.get_nowait()
        except asyncio.QueueEmpty:
            return
    try:
        queue.put_nowait(payload)
    except asyncio.QueueFull:
        return


def decimate(amplitudes: np.ndarray, bins: int = 8) -> list[float]:
    values = np.asarray(amplitudes, dtype=np.float64)
    if bins < 1:
        raise ValueError("bins must be >= 1")
    if values.size <= bins:
        return [float(item) for item in values]
    edges = np.linspace(0, values.size, bins + 1, dtype=int)
    reduced = [float(np.mean(values[edges[index] : edges[index + 1]])) for index in range(bins)]
    return reduced


def follow(
    state: SonarState,
    source: CSISource,
    *,
    hz: float = 10.0,
    bins: int = 8,
    stored_clock: Callable[[], float] | None = None,
) -> list[dict[str, object]]:
    """Snapshots at ``hz`` over simulated time, each with state and a short amplitude vector.

    ``stored_clock`` stamps the history with wall time. The snapshot ``ts`` stays
    on the trace so the panel timeline does not jump to a Unix timestamp.
    """
    if hz <= 0:
        raise ValueError("hz must be positive")
    frames = [frame for frame in source.frames()]
    if not frames:
        return []
    if state.calibration is None:
        state.calibrate(12.0)
    assert state.calibration is not None
    detector = PresenceDetector(
        state.calibration,
        hysteresis=state.config.hysteresis,
        min_motion_s=state.config.min_motion_s,
        min_presence_s=state.config.min_presence_s,
    )
    windows = extract_features(preprocess(frames))
    decisions = [(item.timestamp, detector.update(item)) for item in windows]
    return list(_snapshots(state, frames, decisions, hz=hz, bins=bins, stored_clock=stored_clock))


def _snapshots(
    state: SonarState,
    frames: list[CSIFrame],
    decisions: list,
    *,
    hz: float,
    bins: int,
    stored_clock: Callable[[], float] | None = None,
) -> Iterator[dict[str, object]]:
    period = 1.0 / hz
    cursor = frames[0].timestamp
    end = frames[-1].timestamp
    decision_index = 0
    current = None
    frame_index = 0
    while cursor <= end + 1e-9:
        while frame_index + 1 < len(frames) and frames[frame_index + 1].timestamp <= cursor:
            frame_index += 1
        while decision_index < len(decisions) and decisions[decision_index][0] <= cursor:
            current = decisions[decision_index][1]
            decision_index += 1
        frame = frames[frame_index]
        sample_state = "empty" if current is None else current.state
        score = 0.0 if current is None else current.motion.score
        state._push(
            sample_state,
            score,
            cursor,
            stored_ts=None if stored_clock is None else stored_clock(),
        )
        yield {
            "ts": cursor,
            "state": sample_state,
            "score": score,
            "amplitudes": decimate(frame.amplitudes, bins),
        }
        cursor += period
