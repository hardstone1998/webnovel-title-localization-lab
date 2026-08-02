"""Environment-backed settings for the HTTP service."""

from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]


@dataclass(frozen=True)
class Settings:
    app_name: str
    app_version: str
    environment: str
    log_level: str
    cors_origins: tuple[str, ...]
    default_config_path: Path
    deepseek_config_path: Path

    @property
    def config_profiles(self) -> dict[str, Path]:
        return {
            "default": self.default_config_path,
            "deepseek": self.deepseek_config_path,
        }


def _cors_origins(value: str) -> tuple[str, ...]:
    return tuple(origin.strip() for origin in value.split(",") if origin.strip())


def _load_dotenv(path: Path) -> None:
    """Load simple KEY=VALUE entries without overriding explicit environment values."""

    if not path.is_file():
        return
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", maxsplit=1)
        key = key.strip()
        if not key:
            continue
        os.environ.setdefault(key, value.strip().strip('"').strip("'"))


@lru_cache
def get_settings() -> Settings:
    """Load settings from environment variables without reading secrets from files."""

    _load_dotenv(PROJECT_ROOT / ".env")
    return Settings(
        app_name=os.getenv("APP_NAME", "WebNovel Title Localization API"),
        app_version=os.getenv("APP_VERSION", "0.1.0"),
        environment=os.getenv("APP_ENV", "development"),
        log_level=os.getenv("LOG_LEVEL", "INFO").upper(),
        cors_origins=_cors_origins(os.getenv("CORS_ORIGINS", "")),
        default_config_path=PROJECT_ROOT / "configs" / "title_selection.default.json",
        deepseek_config_path=PROJECT_ROOT / "configs" / "title_selection.deepseek.json",
    )
