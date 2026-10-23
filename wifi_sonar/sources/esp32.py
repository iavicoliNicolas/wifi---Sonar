"""ESP32 CSI adapter. Lines arrive by serial or UDP; broken ones are ignored.

This parses text the operator's own board prints. It does not scan nearby
networks and it does not ship firmware.
"""

import socket
import threading
from collections.abc import Iterable, Iterator

import numpy as np

from wifi_sonar.sources.frame import CSIFrame


def parse_csi_line(line: str) -> CSIFrame | None:
    """Parse ``CSI <node> <timestamp> <rssi> <amp,amp,...> [phase,phase,...]``.

    Returns None for blanks, comments, and anything that is not a full frame.
    """
    text = line.strip()
    if not text or text.startswith("#"):
        return None
    parts = text.split()
    if len(parts) < 5 or parts[0] != "CSI":
        return None
    node_id = parts[1]
    if not node_id:
        return None
    try:
        timestamp = float(parts[2])
        rssi = float(parts[3])
        amplitudes = _numbers(parts[4])
        phases = None
        if len(parts) >= 6 and parts[5] != "-":
            phases = _numbers(parts[5])
            if phases.shape != amplitudes.shape:
                return None
    except ValueError:
        return None
    if amplitudes.size < 1:
        return None
    return CSIFrame(
        timestamp=timestamp,
        rssi=rssi,
        amplitudes=amplitudes,
        phases=phases,
        node_id=node_id,
    )


def _numbers(text: str) -> np.ndarray:
    items = [item for item in text.split(",") if item != ""]
    if not items:
        raise ValueError("empty list")
    return np.asarray([float(item) for item in items], dtype=np.float64)


class ESP32Source:
    """Yield frames from an iterable of text lines (a serial port or UDP text)."""

    def __init__(self, lines: Iterable[str]) -> None:
        self.lines = lines

    def frames(self) -> Iterator[CSIFrame]:
        for line in self.lines:
            frame = parse_csi_line(line)
            if frame is not None:
                yield frame


def udp_lines(
    port: int,
    *,
    host: str = "0.0.0.0",
    stop: threading.Event | None = None,
) -> Iterator[str]:
    """Yield datagrams as text. Bind this only when your own board is sending."""
    if port < 1 or port > 65535:
        raise ValueError("port must be between 1 and 65535")
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.settimeout(0.3)
    try:
        sock.bind((host, port))
        while stop is None or not stop.is_set():
            try:
                data, _addr = sock.recvfrom(65535)
            except TimeoutError:
                continue
            text = data.decode("utf-8", errors="replace")
            for line in text.splitlines():
                if line.strip():
                    yield line
    finally:
        sock.close()
