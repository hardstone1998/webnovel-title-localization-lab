from __future__ import annotations

import os

import pytest
from app.config.pipeline_config import load_config
from app.config.settings import _load_dotenv, _pipeline_config_path
from app.domain.errors import ValidationError


def test_dotenv_loader_uses_file_values_without_overriding_environment(
    tmp_path, monkeypatch
) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text("APP_NAME=from-file\nLOG_LEVEL=DEBUG\n", encoding="utf-8")
    monkeypatch.setenv("APP_NAME", "from-environment")
    monkeypatch.delenv("LOG_LEVEL", raising=False)

    _load_dotenv(env_file)

    assert os.environ["APP_NAME"] == "from-environment"
    assert os.environ["LOG_LEVEL"] == "DEBUG"


def test_pipeline_config_path_accepts_project_relative_override(project_root) -> None:
    assert _pipeline_config_path("configs/title_selection.baseline_v0.json") == (
        project_root / "configs" / "title_selection.baseline_v0.json"
    )


def test_provider_profile_uses_explicit_environment_configuration(
    project_root, monkeypatch
) -> None:
    monkeypatch.setenv("LLM_MODEL", "test-model")
    monkeypatch.setenv("LLM_BASE_URL", "https://llm.example/v1")
    monkeypatch.setenv("LLM_TIMEOUT_SECONDS", "45")
    monkeypatch.setenv("LLM_MAX_TOKENS", "12000")

    config = load_config(project_root / "configs/title_selection.default.json")

    assert config.provider == {
        "model": "test-model",
        "base_url": "https://llm.example/v1",
        "api_key_env": "LLM_API_KEY",
        "timeout_seconds": 45,
        "max_tokens": 12000,
    }


def test_provider_max_tokens_must_be_positive(project_root, monkeypatch) -> None:
    monkeypatch.setenv("LLM_MAX_TOKENS", "0")

    with pytest.raises(ValidationError) as error:
        load_config(project_root / "configs/title_selection.default.json")

    assert error.value.code == "INVALID_CONFIGURATION_VALUE"
    assert error.value.details["field"] == "provider.max_tokens"
