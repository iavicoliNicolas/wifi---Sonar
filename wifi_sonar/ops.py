"""Reconnect a source, write one JSON log line, refresh a quiet baseline."""

import json
import logging
from collections.abc import Callable, Iterator

from wifi_sonar.sources.base import CSISource
from wifi_sonar.sources.frame import CSIFrame

logger = logging.getLogger("wifi_sonar")


def log_event(event: str, **fields: object) -> None:
    """One JSON object per line. Fields stay local; this is not telemetry."""
    logger.info(json.dumps({"event": event, **fields}, ensure_ascii=False, default=str))


def iter_resilient(
    open_source: Callable[[], CSISource],
    *,
    retries: int = 3,
) -> Iterator[CSIFrame]:
    """Yield frames, and open the source again after a dropped link.

    The process that calls this stays up. ``retries`` counts drops, not frames.
    """
    if retries < 0:
        raise ValueError("retries must be >= 0")
    drops = 0
    while True:
        try:
            yield from open_source().frames()
            return
        except ConnectionError as exc:
            drops += 1
            log_event("source dropped", attempt=drops, reason=str(exc))
            if drops > retries:
                raise
