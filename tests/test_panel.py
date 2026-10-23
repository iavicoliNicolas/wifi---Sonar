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
    script = client.get("/static/app.js")
    assert "/ws" in script.text
