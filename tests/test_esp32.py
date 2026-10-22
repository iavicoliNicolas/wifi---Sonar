import socket
import threading
from pathlib import Path

from wifi_sonar.engine import build_source
from wifi_sonar.models import CSIFrame
from wifi_sonar.settings import Settings
from wifi_sonar.sources.esp32 import ESP32Source, parse_csi_line


def _classic_line() -> str:
    fields = ["CSI_DATA", "7", "aa:bb:cc:dd:ee:ff", "-42", *["1"] * 20]
    fields[18] = "2500000"
    return ",".join(fields) + ',"[0,3,4,0]"'


def _c5_line() -> str:
    fields = ["CSI_DATA", "1", "11:22:33:44:55:66", "-20", *["0"] * 10]
    fields[9] = "1000000"
    return ",".join(fields) + ',"[0,2]"'


def test_parser_reads_official_and_compact_lines_and_skips_garbage():
    classic = parse_csi_line(_classic_line())
    assert classic is not None
    assert classic.node_id == "aa:bb:cc:dd:ee:ff"
    assert classic.rssi == -42
    assert classic.timestamp == 2.5
    assert classic.amplitudes == (3.0, 4.0)

    compact = parse_csi_line("CSI,living,1.25,-48,1.5|2.5,0.1|-0.2")
    assert compact is not None
    assert compact.node_id == "living"
    assert compact.amplitudes == (1.5, 2.5)
    assert compact.phases == (0.1, -0.2)

    newer = parse_csi_line(_c5_line())
    assert newer is not None
    assert newer.timestamp == 1.0
    assert newer.amplitudes == (2.0,)

    garbage = [
        "",
        "# comentario",
        "no-es-csi",
        "CSI,solo,tres",
        "CSI,nodo,nope,-40,1|2",
        "CSI,nodo,1.0,-40,1|x|3",
        "CSI,nodo,1.0,-40,1|2,0.1",
        "CSI_DATA,roto",
        'CSI_DATA,0,mac,-1,"[1]"',
    ]
    assert all(parse_csi_line(line) is None for line in garbage)


def test_source_skips_corrupt_lines_from_a_file(tmp_path: Path):
    path = tmp_path / "serial.txt"
    path.write_text(
        "\n".join(
            [
                "basura",
                "CSI,cocina,0.5,-51,1|0|2",
                "CSI,cocina,0.6,no",
                _classic_line(),
            ]
        ),
        encoding="utf-8",
    )
    frames = list(ESP32Source(serial_path=path, sample_rate_hz=20).frames())
    assert [frame.node_id for frame in frames] == ["cocina", "aa:bb:cc:dd:ee:ff"]
    assert frames[0].n_subcarriers == 3


def test_udp_datagram_becomes_a_frame():
    probe = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    probe.bind(("127.0.0.1", 0))
    port = probe.getsockname()[1]
    probe.close()
    source = ESP32Source(udp_host="127.0.0.1", udp_port=port)
    found: list[CSIFrame] = []

    def collect() -> None:
        for frame in source.frames():
            found.append(frame)
            break

    thread = threading.Thread(target=collect, daemon=True)
    thread.start()
    thread.join(0.05)
    sender = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    payload = b"ruido\nCSI,nodo,1.5,-40,1|2|3\n"
    for _ in range(20):
        sender.sendto(payload, ("127.0.0.1", port))
        thread.join(0.05)
        if found:
            break
    sender.close()
    thread.join(1.0)
    assert found
    assert found[0].node_id == "nodo"
    assert found[0].amplitudes == (1.0, 2.0, 3.0)


def test_build_source_uses_the_serial_path(tmp_path: Path):
    path = tmp_path / "vacio.txt"
    path.write_text("", encoding="utf-8")
    source = build_source(Settings(source="esp32", esp32_serial=str(path)))
    assert isinstance(source, ESP32Source)
    assert list(source.frames()) == []
