"""Líneas CSI de un ESP32: CSV de esp-csi o el formato corto por UDP/serial."""

from __future__ import annotations

import math
import socket
from collections.abc import Iterable, Iterator
from pathlib import Path

from wifi_sonar.models import CSIFrame

# CSV clásico de examples/get-started (ESP32 / C3): local_timestamp en la columna 18.
_CLASSIC_TIMESTAMP = 18
# CSV de ESP32-C5 / C6: local_timestamp en la columna 9.
_C5_TIMESTAMP = 9


def parse_csi_line(line: str) -> CSIFrame | None:
    """Devuelve un frame o None si la línea está vacía, es un comentario o está rota.

    No levanta: una línea corrupta no debe cortar el stream.
    """

    text = line.strip()
    if not text or text.startswith("#"):
        return None
    if text.startswith("CSI_DATA,"):
        return _parse_official(text)
    if text.startswith("CSI,"):
        return _parse_compact(text)
    return None


def _parse_compact(text: str) -> CSIFrame | None:
    parts = text.split(",")
    if len(parts) not in (5, 6):
        return None
    try:
        node_id = parts[1].strip()
        timestamp = float(parts[2])
        rssi = float(parts[3])
        amplitudes = _pipe_floats(parts[4])
        phases = None if len(parts) == 5 else _pipe_floats(parts[5])
        if not node_id or not amplitudes:
            return None
        if phases is not None and len(phases) != len(amplitudes):
            return None
        return CSIFrame(
            timestamp=timestamp,
            rssi=rssi,
            amplitudes=amplitudes,
            phases=phases,
            node_id=node_id,
        )
    except (ValueError, OverflowError):
        return None


def _parse_official(text: str) -> CSIFrame | None:
    start = text.find("[")
    end = text.rfind("]")
    if start < 0 or end <= start:
        return None
    prefix = text[:start].rstrip(' ,"')
    fields = prefix.split(",")
    if len(fields) < 4 or fields[0] != "CSI_DATA":
        return None
    if len(fields) >= _CLASSIC_TIMESTAMP + 2:
        timestamp_index = _CLASSIC_TIMESTAMP
    elif len(fields) >= _C5_TIMESTAMP + 2:
        timestamp_index = _C5_TIMESTAMP
    else:
        return None
    try:
        node_id = fields[2].strip()
        rssi = float(fields[3])
        timestamp = float(fields[timestamp_index]) / 1_000_000.0
        samples = [_float_token(token) for token in text[start + 1 : end].split(",")]
    except (ValueError, OverflowError):
        return None
    if not node_id or len(samples) < 2:
        return None
    if len(samples) % 2:
        samples = samples[:-1]
    amplitudes: list[float] = []
    phases: list[float] = []
    for index in range(0, len(samples), 2):
        imag = samples[index]
        real = samples[index + 1]
        amplitudes.append(math.hypot(real, imag))
        phases.append(math.atan2(imag, real))
    try:
        return CSIFrame(
            timestamp=timestamp,
            rssi=rssi,
            amplitudes=tuple(amplitudes),
            phases=tuple(phases),
            node_id=node_id,
        )
    except ValueError:
        return None


def _pipe_floats(text: str) -> tuple[float, ...]:
    tokens = [token for token in text.split("|") if token != ""]
    if not tokens:
        raise ValueError("empty list")
    return tuple(float(token) for token in tokens)


def _float_token(token: str) -> float:
    cleaned = token.strip().strip('"')
    if not cleaned:
        raise ValueError("empty sample")
    return float(cleaned)


class ESP32Source:
    """Lee CSI por una lista de líneas, un archivo/tty o un socket UDP.

    El puerto serie se abre como archivo de texto. No usa pyserial: un tty ya
    configurado o un FIFO alcanzan. UDP es el camino pensado para más de una placa.
    """

    def __init__(
        self,
        lines: Iterable[str] | None = None,
        serial_path: str | Path | None = None,
        udp_host: str | None = None,
        udp_port: int | None = None,
        sample_rate_hz: float = 100.0,
    ) -> None:
        if sample_rate_hz <= 0:
            raise ValueError("sample_rate_hz must be positive")
        self._lines = lines
        self.serial_path = None if serial_path is None else Path(serial_path)
        self.udp_host = udp_host
        self.udp_port = udp_port
        self._sample_rate_hz = sample_rate_hz

    @property
    def sample_rate_hz(self) -> float:
        return self._sample_rate_hz

    def frames(self) -> Iterator[CSIFrame]:
        if self._lines is not None:
            yield from _frames_from_lines(self._lines)
            return
        if self.serial_path is not None:
            with self.serial_path.open(encoding="utf-8", errors="replace") as handle:
                yield from _frames_from_lines(handle)
            return
        if self.udp_host is None or self.udp_port is None:
            raise ValueError("esp32 source needs lines, a serial path, or a UDP port")
        yield from self._udp_frames()

    def _udp_frames(self) -> Iterator[CSIFrame]:
        assert self.udp_host is not None and self.udp_port is not None
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            sock.bind((self.udp_host, self.udp_port))
            sock.settimeout(1.0)
            while True:
                try:
                    payload, _addr = sock.recvfrom(65535)
                except TimeoutError:
                    continue
                text = payload.decode("utf-8", errors="replace")
                yield from _frames_from_lines(text.splitlines())
        finally:
            sock.close()


def _frames_from_lines(lines: Iterable[str]) -> Iterator[CSIFrame]:
    for line in lines:
        frame = parse_csi_line(line)
        if frame is not None:
            yield frame
