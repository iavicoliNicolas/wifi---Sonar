from wifi_sonar.pipeline import collect
from wifi_sonar.sources.esp32 import ESP32Source, parse_csi_line

SAMPLE = "CSI living 1.5 -47 1.0,1.1,0.9 0.1,0.2,0.0"


def test_parser_reads_a_fictional_line_and_skips_garbage() -> None:
    frame = parse_csi_line(SAMPLE)
    assert frame is not None
    assert frame.node_id == "living"
    assert frame.rssi == -47
    assert frame.n_subcarriers == 3
    assert parse_csi_line("") is None
    assert parse_csi_line("# comment") is None
    assert parse_csi_line("CSI living nope") is None
    assert parse_csi_line("CSI living 1.0 -40 1,2,3 0.1,0.2") is None
    assert parse_csi_line("not a frame at all") is None


def test_source_keeps_the_good_lines() -> None:
    lines = [
        "noise {{{",
        SAMPLE,
        "CSI living 1.6 -48 1,2,3 0.1,0.2",
        "CSI living 2.0 -46 1.2,1.0,0.8 -",
    ]
    frames = collect(ESP32Source(lines))
    assert [frame.timestamp for frame in frames] == [1.5, 2.0]
    assert frames[1].phases is None
