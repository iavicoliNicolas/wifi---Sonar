"""Arranque local: `python -m wifi_sonar` o el comando `wifi-sonar`."""

from __future__ import annotations

import uvicorn

from wifi_sonar.settings import Settings


def main() -> None:
    settings = Settings.from_env()
    uvicorn.run(
        "wifi_sonar.api.app:app",
        host=settings.host,
        port=settings.port,
        log_level="info",
    )


if __name__ == "__main__":
    main()
