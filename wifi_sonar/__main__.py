"""Run the local panel and API. The simulator is the source until hardware exists."""

import uvicorn

from wifi_sonar.api import create_app
from wifi_sonar.live import start_live
from wifi_sonar.runtime import SonarConfig, SonarState


def main() -> None:
    # 16 carriers keep the panel responsive. The detector is the same one tested at 52.
    state = SonarState(config=SonarConfig(n_subcarriers=16))
    app = create_app(state)
    start_live(app)
    uvicorn.run(app, host="0.0.0.0", port=8000)


if __name__ == "__main__":
    main()
