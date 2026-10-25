"""Local HTTP API. Nothing here leaves the machine."""

from pathlib import Path

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from wifi_sonar.api.stream import FrameHub
from wifi_sonar.detect.calibrate import quality_report
from wifi_sonar.recording import save_recent
from wifi_sonar.runtime import SonarConfig, SonarState

WEB_ROOT = Path(__file__).resolve().parents[2] / "web"


def _recordings_dir(sonar: SonarState) -> Path:
    store = sonar.store
    if store is not None:
        return Path(store.path).parent / "recordings"
    return Path("data/recordings")


class CalibrateBody(BaseModel):
    seconds: float = Field(default=12.0, gt=0.0, le=120.0)


class SensingBody(BaseModel):
    paused: bool


def create_app(state: SonarState | None = None) -> FastAPI:
    app = FastAPI(
        title="wifi-sonar",
        summary="Presencia y movimiento a partir del WiFi de esta red.",
        version="0.0.1",
    )
    app.state.sonar = state or SonarState()
    app.state.hub = FrameHub()

    @app.get("/health")
    def health() -> dict[str, object]:
        sonar = app.state.sonar
        return {
            "ok": True,
            "paused": sonar.paused,
            "source": getattr(app.state, "source_status", "up"),
        }

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
            "quality": quality_report(calibration),
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

    @app.delete("/history")
    def wipe_history() -> dict[str, bool]:
        app.state.sonar.wipe()
        return {"cleared": True}

    @app.post("/recording")
    def recording() -> dict[str, object]:
        sonar = app.state.sonar
        folder = _recordings_dir(sonar)
        try:
            path = save_recent(list(sonar.recent), folder)
        except ValueError as exc:
            raise HTTPException(status_code=409, detail="no hay traza reciente") from exc
        return {"frames": len(sonar.recent), "file": path.name}

    @app.post("/sensing")
    def set_sensing(body: SensingBody) -> dict[str, object]:
        sonar = app.state.sonar
        sonar.paused = body.paused
        sonar.latest["sensing"] = not body.paused
        return {"paused": sonar.paused, "retention_s": sonar.config.retention_s}

    @app.get("/")
    def panel() -> FileResponse:
        return FileResponse(WEB_ROOT / "index.html")

    @app.get("/favicon.ico")
    def favicon() -> FileResponse:
        return FileResponse(WEB_ROOT / "favicon.png", media_type="image/png")

    app.mount("/static", StaticFiles(directory=WEB_ROOT), name="static")

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
