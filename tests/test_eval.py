from wifi_sonar.eval.report import compute_metrics, render_report, write_report


def test_eval_table_meets_the_simulator(tmp_path):
    metrics = compute_metrics()
    text = render_report(metrics)
    assert "| Escenario | Métrica | Valor |" in text
    by_name = {(row.scenario, row.name): row.value for row in metrics}

    assert by_name[("caminatas", "recall")] >= 0.95
    assert by_name[("caminatas", "precisión")] >= 0.95
    assert by_name[("quietud", "recall")] == 1.0
    assert by_name[("quietud", "precisión")] == 1.0
    assert by_name[("cuarto vacío 120 s", "falsos positivos de movimiento")] <= 1
    assert by_name[("cuarto vacío 120 s", "falsos positivos de presencia")] <= 1
    assert by_name[("caminatas", "latencia mediana (s)")] >= 0

    destination = tmp_path / "eval.md"
    assert write_report(destination, metrics) == text
    assert destination.read_text(encoding="utf-8") == text
