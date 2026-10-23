from fastapi.testclient import TestClient
from wifi_sonar.api import create_app
from wifi_sonar.runtime import SonarConfig, SonarState


def test_panel_shell_is_served() -> None:
    client = TestClient(create_app(SonarState(config=SonarConfig(n_subcarriers=8))))
    page = client.get("/")
    assert page.status_code == 200
    assert 'id="state"' in page.text
    assert "vacío" in page.text
    css = client.get("/static/style.css")
    assert css.status_code == 200
    assert "--motion" in css.text
    assert "clamp(3.2rem, 8vw, 5.6rem)" in css.text
    script = client.get("/static/app.js")
    assert "/ws" in script.text
    assert "HEAT_COLS = 180" in script.text
    assert "requestAnimationFrame" in script.text
    assert 'id="heatmap"' in page.text
    assert 'id="scoreboard"' in page.text
    assert 'id="timeline"' in page.text
    assert 'id="cal-start"' in page.text
    assert "salí de la habitación" in script.text
    assert 'id="sensibility"' in page.text
    assert 'id="window"' in page.text
    assert 'id="hysteresis"' in page.text
    assert 'id="notify"' in page.text
    assert "Notification" in script.text
    assert "sensado activo" in page.text
    assert 'id="pause"' in page.text
    assert 'id="wipe"' in page.text
    assert 'id="zones"' in page.text
