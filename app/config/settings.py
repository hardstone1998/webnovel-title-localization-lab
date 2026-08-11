"""Environment-backed settings for the HTTP service."""

from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
_project_dotenv_loaded = False


@dataclass(frozen=True)
class Settings:
    app_name: str
    app_version: str
    environment: str
    log_level: str
    cors_origins: tuple[str, ...]
    pipeline_config_path: Path


def _cors_origins(value: str) -> tuple[str, ...]:
    return tuple(origin.strip() for origin in value.split(",") if origin.strip())


def _pipeline_config_path(value: str | None) -> Path:
    if not value or not value.strip():
        return PROJECT_ROOT / "configs" / "title_selection.default.json"
    configured = Path(value.strip())
    return configured if configured.is_absolute() else PROJECT_ROOT / configured


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


def load_project_dotenv() -> None:
    """Load the project's local environment file once, if it exists."""

    global _project_dotenv_loaded
    if _project_dotenv_loaded:
        return
    _load_dotenv(PROJECT_ROOT / ".env")
    _project_dotenv_loaded = True


@lru_cache
def get_settings() -> Settings:
    """Load settings from environment variables and the local ``.env`` file."""

    load_project_dotenv()
    return Settings(
        app_name=os.getenv("APP_NAME", "WebNovel Title Localization API"),
        app_version=os.getenv("APP_VERSION", "0.1.0"),
        environment=os.getenv("APP_ENV", "development"),
        log_level=os.getenv("LOG_LEVEL", "INFO").upper(),
        cors_origins=_cors_origins(os.getenv("CORS_ORIGINS", "")),
        pipeline_config_path=_pipeline_config_path(os.getenv("PIPELINE_CONFIG_PATH")),
    )
