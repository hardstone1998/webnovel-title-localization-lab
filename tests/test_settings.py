from __future__ import annotations

import os

from app.config.settings import _load_dotenv


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
