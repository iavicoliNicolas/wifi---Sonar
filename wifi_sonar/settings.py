"""Configuración del proceso y del detector."""

from __future__ import annotations

import os
from dataclasses import asdict, dataclass, field


@dataclass(slots=True)
class AppConfig:
    sensitivity: float = 1.0
    window_s: float = 2.0
    step_s: float = 0.5
    spectrum_window_s: float = 10.0
    hysteresis: float = 0.35
    on_threshold: float = 0.75
    min_duration_s: float = 1.0
    presence_min_duration_s: float = 3.0
    threshold_k: float = 8.0
    retention_days: int = 30
    paused: bool = False
    webhook_url: str = ""
    fusion: str = "or"
    zones: dict[str, str] = field(default_factory=dict)
    mode: str = "csi"

    def __post_init__(self) -> None:
        if not 0.2 <= self.sensitivity <= 3.0:
            raise ValueError("sensitivity must be between 0.2 and 3")
        if not 0.5 <= self.window_s <= 5.0:
            raise ValueError("window_s must be between 0.5 and 5")
        if not 0.1 <= self.step_s <= 2.0:
            raise ValueError("step_s must be between 0.1 and 2")
        if not 4.0 <= self.spectrum_window_s <= 30.0:
            raise ValueError("spectrum_window_s must be between 4 and 30")
        if not 0.0 <= self.hysteresis <= 0.9:
            raise ValueError("hysteresis must be between 0 and 0.9")
        if not 0.05 <= self.on_threshold <= 1.0:
            raise ValueError("on_threshold must be between 0.05 and 1")
        if self.min_duration_s < 0 or self.presence_min_duration_s < 0:
            raise ValueError("durations must be >= 0")
        if self.threshold_k < 0:
            raise ValueError("threshold_k must be >= 0")
        if self.retention_days < 1:
            raise ValueError("retention_days must be >= 1")
        if self.fusion not in ("or", "vote"):
            raise ValueError("fusion must be or or vote")
        if self.mode not in ("csi", "rssi"):
            raise ValueError("mode must be csi or rssi")
        if self.hysteresis > self.on_threshold:
            raise ValueError("hysteresis cannot exceed on_threshold")

    def to_dict(self) -> dict[str, object]:
        return asdict(self)

    def merged(self, updates: dict[str, object]) -> AppConfig:
        data = self.to_dict()
        data.update(updates)
        return AppConfig(**data)


@dataclass(frozen=True, slots=True)
class Settings:
    host: str = "127.0.0.1"
    port: int = 8000
    db_path: str = "data/wifi_sonar.sqlite"
    source: str = "sim"
    seed: int = 0
    speed: float = 1.0
    auto_start: bool = True
    replay_path: str = ""
    esp32_host: str = "0.0.0.0"
    esp32_port: int = 5005
    esp32_serial: str = ""
    recordings_dir: str = "data/recordings"
    rssi_devices: str = "telefono"

    @classmethod
    def from_env(cls) -> Settings:
        def env(name: str, default: str) -> str:
            return os.environ.get(name, default)

        return cls(
            host=env("WIFI_SONAR_HOST", "127.0.0.1"),
            port=int(env("WIFI_SONAR_PORT", "8000")),
            db_path=env("WIFI_SONAR_DB", "data/wifi_sonar.sqlite"),
            source=env("WIFI_SONAR_SOURCE", "sim"),
            seed=int(env("WIFI_SONAR_SEED", "0")),
            speed=float(env("WIFI_SONAR_SPEED", "1.0")),
            auto_start=env("WIFI_SONAR_AUTOSTART", "1") not in ("0", "false", "False"),
            replay_path=env("WIFI_SONAR_REPLAY", ""),
            esp32_host=env("WIFI_SONAR_ESP32_HOST", "0.0.0.0"),
            esp32_port=int(env("WIFI_SONAR_ESP32_PORT", "5005")),
            esp32_serial=env("WIFI_SONAR_ESP32_SERIAL", ""),
            recordings_dir=env("WIFI_SONAR_RECORDINGS", "data/recordings"),
            rssi_devices=env("WIFI_SONAR_RSSI_DEVICES", "telefono"),
        )
