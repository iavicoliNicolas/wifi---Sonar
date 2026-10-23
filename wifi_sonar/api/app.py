"""Local HTTP API. Nothing here leaves the machine."""

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from pydantic import BaseModel, Field

from wifi_sonar.api.stream import FrameHub
from wifi_sonar.runtime import SonarConfig, SonarState


class CalibrateBody(BaseModel):
    seconds: float = Field(default=12.0, gt=0.0, le=120.0)


def create_app(state: SonarState | None = None) -> FastAPI:
    app = FastAPI(
        title="wifi-sonar",
        summary="Presencia y movimiento a partir del WiFi de esta red.",
        version="0.0.1",
    )
    app.state.sonar = state or SonarState()
    app.state.hub = FrameHub()

    @app.get("/status")
    def status() -> dict[str, object]:
        current = app.state.sonar.latest
        return {**current, "sensing": not app.state.sonar.paused}

    @app.post("/calibrate")
    def calibrate(body: CalibrateBody) -> dict[str, object]:
        try:
            calibration = app.state.sonar.calibrate(body.seconds)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return {
            "seconds": calibration.seconds,
            "k": calibration.k,
            "thresholds": calibration.thresholds,
        }

    @app.get("/config")
    def get_config() -> SonarConfig:
        return app.state.sonar.config

    @app.put("/config")
    def put_config(config: SonarConfig) -> SonarConfig:
        app.state.sonar.replace_config(config)
        return config

    @app.get("/history")
    def history() -> list[dict[str, object]]:
        return list(app.state.sonar.history)

    @app.websocket("/ws")
    async def websocket_endpoint(socket: WebSocket) -> None:
        await socket.accept()
        queue = app.state.hub.subscribe()
        try:
            while True:
                payload = await queue.get()
                await socket.send_json(payload)
        except WebSocketDisconnect:
            app.state.hub.unsubscribe(queue)

    return app
