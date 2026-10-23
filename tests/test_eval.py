from wifi_sonar.eval import evaluate


def test_eval_report_covers_motion_and_presence(tmp_path) -> None:
    report = evaluate(tmp_path / "eval.md")
    text = (tmp_path / "eval.md").read_text(encoding="utf-8")
    assert text == report
    assert "Precisión" in report
    assert "Recall" in report
    assert "Latencia" in report
    motion = _row(report, "motion")
    presence = _row(report, "presence")
    assert motion[0] >= 0.95
    assert motion[1] >= 0.95
    assert presence[0] >= 0.95
    assert presence[1] >= 0.95


def _row(report: str, name: str) -> tuple[float, float]:
    for line in report.splitlines():
        if line.startswith(f"| {name} "):
            cells = [cell.strip() for cell in line.strip("|").split("|")]
            return float(cells[1]), float(cells[2])
    raise AssertionError(f"missing row {name}")
