"""HTTP local: estado, calibración, config e historial."""

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Query, WebSocket, WebSocketDisconnect
from pydantic import BaseModel, Field

from wifi_sonar import __version__
from wifi_sonar.engine import Engine
from wifi_sonar.settings import Settings
from wifi_sonar.storage.sqlite import SqliteStore
from wifi_sonar.stream import SnapshotHub


class CalibrateBody(BaseModel):
    seconds: float = Field(default=20.0, gt=0, le=180)


class ConfigUpdate(BaseModel):
    sensitivity: float | None = None
    window_s: float | None = None
    step_s: float | None = None
    spectrum_window_s: float | None = None
    hysteresis: float | None = None
    on_threshold: float | None = None
    min_duration_s: float | None = None
    presence_min_duration_s: float | None = None
    threshold_k: float | None = None
    retention_days: int | None = None
    paused: bool | None = None
    webhook_url: str | None = None
    fusion: str | None = None
    zones: dict[str, str] | None = None
    mode: str | None = None


def create_app(settings: Settings | None = None, engine: Engine | None = None) -> FastAPI:
    settings = settings if settings is not None else Settings.from_env()
    if engine is None:
        engine = Engine(settings, store=SqliteStore(settings.db_path))
    hub = SnapshotHub()
    engine.add_listener(hub.publish)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        if app.state.settings.auto_start:
            app.state.engine.start()
        yield
        app.state.engine.stop()

    app = FastAPI(
        title="WiFi Sonar",
        version=__version__,
        description=(
            "Presencia y movimiento en el hogar propio. "
            "El procesamiento queda en la máquina local y no hay telemetría."
        ),
        lifespan=lifespan,
    )
    app.state.settings = settings
    app.state.engine = engine
    app.state.hub = hub

    @app.get("/status")
    def status() -> dict[str, object]:
        return engine.status()

    @app.post("/calibrate")
    def calibrate(body: CalibrateBody) -> dict[str, object]:
        try:
            calibration = engine.calibrate(body.seconds)
        except ValueError as error:
            raise HTTPException(status_code=400, detail=str(error)) from error
        payload = calibration.to_dict()
        mean = calibration.mean["motion_energy"]
        spread = calibration.std["motion_energy"]
        ratio = spread / mean if mean else 0.0
        payload["quality"] = "estable" if ratio < 0.8 else "ruidosa"
        return payload

    @app.get("/config")
    def get_config() -> dict[str, object]:
        return engine.config.to_dict()

    @app.put("/config")
    def put_config(body: ConfigUpdate) -> dict[str, object]:
        updates = body.model_dump(exclude_none=True)
        try:
            updated = engine.update_config(updates)
        except (TypeError, ValueError) as error:
            raise HTTPException(status_code=422, detail=str(error)) from error
        return updated.to_dict()

    @app.get("/history")
    def history(limit: int = Query(default=100, ge=1, le=1000)) -> list[dict[str, object]]:
        return engine.store.list_events(limit)

    @app.websocket("/ws")
    async def stream(socket: WebSocket) -> None:
        await socket.accept()
        try:
            await socket.send_json(engine.status())
            while True:
                snapshot = hub.take()
                if snapshot is not None:
                    await socket.send_json(snapshot)
                await asyncio.sleep(0.1)
        except WebSocketDisconnect:
            return

    return app


app = create_app()
