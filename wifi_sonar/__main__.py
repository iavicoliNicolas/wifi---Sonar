"""Run the local panel and API. The simulator is the source until hardware exists."""

import os
from pathlib import Path

import uvicorn

from wifi_sonar.api import create_app
from wifi_sonar.ingress import start_udp, udp_port_from_env
from wifi_sonar.live import start_live
from wifi_sonar.runtime import SonarConfig, SonarState
from wifi_sonar.storage import Store


def main() -> None:
    # 16 carriers keep the panel responsive. The detector is the same one tested at 52.
    path = Path(os.environ.get("WIFI_SONAR_DB", "data/sonar.sqlite"))
    path.parent.mkdir(parents=True, exist_ok=True)
    state = SonarState(config=SonarConfig(n_subcarriers=16), store=Store(path))
    app = create_app(state)
    udp_port = udp_port_from_env()
    if udp_port is None:
        start_live(app)
    else:
        start_udp(app, udp_port)
    uvicorn.run(app, host="0.0.0.0", port=8000)


if __name__ == "__main__":
    main()
