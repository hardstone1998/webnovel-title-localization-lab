from __future__ import annotations

import json

import pytest
from jsonschema import Draft202012Validator

from title_localization_lab.adapters import OpenAICompatibleAdapter
from title_localization_lab.artifacts import atomic_write_json, read_json
from title_localization_lab.cli import main
from title_localization_lab.config import load_config
from title_localization_lab.errors import ProviderError
from title_localization_lab.orchestration import run_pipeline


class StubHTTPResponse:
    def __init__(self, payload: dict[str, object]) -> None:
        self.payload = json.dumps(payload).encode("utf-8")

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback) -> None:
        return None

    def read(self) -> bytes:
        return self.payload


def test_deterministic_pipeline_writes_schema_valid_artifacts(
    project_root,
    tmp_path,
) -> None:
    outcome = run_pipeline(
        project_root / "data/examples/sample_title_case.json",
        project_root / "configs/title_selection.default.json",
        tmp_path,
    )
    candidate_data = read_json(outcome.candidate_path)
    ranking_data = read_json(outcome.ranking_path)
    candidate_schema = read_json(project_root / "data/schemas/candidate_set.schema.json")
    ranking_schema = read_json(project_root / "data/schemas/ranking_result.schema.json")
    Draft202012Validator(candidate_schema).validate(candidate_data)
    Draft202012Validator(ranking_schema).validate(ranking_data)
    assert len(candidate_data["candidates"]) == 12
    assert len(ranking_data["scores"]) == 12
    assert ranking_data["winner_candidate_id"]
    assert outcome.report_path.read_text(encoding="utf-8").startswith("# 英文剧名生成与评分报告")


def test_cli_runs_offline(project_root, tmp_path, capsys, monkeypatch) -> None:
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)

    def fail_if_network_is_used(*args, **kwargs):
        raise AssertionError("deterministic adapter attempted network access")

    monkeypatch.setattr(
        "title_localization_lab.adapters.urllib.request.urlopen",
        fail_if_network_is_used,
    )
    exit_code = main(
        [
            "--input",
            str(project_root / "data/examples/sample_title_case.json"),
            "--config",
            str(project_root / "configs/title_selection.default.json"),
            "--output-dir",
            str(tmp_path),
            "--adapter",
            "deterministic",
        ]
    )
    output = json.loads(capsys.readouterr().out)
    assert exit_code == 0
    assert output["outcome"] == "winner_selected"


def test_deepseek_provider_preset_loads_without_a_credential_value(project_root) -> None:
    config_path = project_root / "configs/title_selection.deepseek.json"
    raw_config = read_json(config_path)
    config = load_config(config_path)

    assert config.provider == {
        "model": "deepseek-v4-flash",
        "base_url": "https://api.deepseek.com",
        "api_key_env": "DEEPSEEK_API_KEY",
        "timeout_seconds": 120,
    }
    assert "api_key" not in raw_config["provider"]
    assert "DEEPSEEK_API_KEY" in config_path.read_text(encoding="utf-8")


def test_deepseek_request_uses_openai_compatible_json_contract(
    project_root,
    tmp_path,
    monkeypatch,
) -> None:
    sentinel_key = "test-only-deepseek-secret"
    captured: dict[str, object] = {}
    envelope = {
        "id": "response-test",
        "choices": [
            {
                "message": {
                    "content": json.dumps({"titles": ["A Tested Title"]}),
                }
            }
        ],
    }

    def fake_urlopen(request, timeout):
        captured["request"] = request
        captured["timeout"] = timeout
        return StubHTTPResponse(envelope)

    config = load_config(project_root / "configs/title_selection.deepseek.json")
    monkeypatch.setenv("DEEPSEEK_API_KEY", sentinel_key)
    monkeypatch.setattr(
        "title_localization_lab.adapters.urllib.request.urlopen",
        fake_urlopen,
    )

    value, metadata = OpenAICompatibleAdapter(config.provider)._request_json(
        '只返回 JSON：{"titles":["..."]}。'
    )

    request = captured["request"]
    body = json.loads(request.data.decode("utf-8"))
    assert request.full_url == "https://api.deepseek.com/chat/completions"
    assert request.get_header("Authorization") == f"Bearer {sentinel_key}"
    assert body["model"] == "deepseek-v4-flash"
    assert "json" in body["messages"][0]["content"].lower()
    assert body["response_format"] == {"type": "json_object"}
    assert captured["timeout"] == 120
    assert value == {"titles": ["A Tested Title"]}
    assert metadata == {
        "adapter": "openai-compatible",
        "response_id": "response-test",
        "base_url": "https://api.deepseek.com",
    }

    representative_artifact = atomic_write_json(
        tmp_path / "provider_artifact.json",
        {
            "public_config": config.public_dict(),
            "provider_metadata": metadata,
        },
    )
    assert sentinel_key not in representative_artifact.read_text(encoding="utf-8")


def test_deepseek_missing_credential_writes_safe_error(
    project_root,
    tmp_path,
    monkeypatch,
) -> None:
    sentinel_key = "test-only-deepseek-secret"
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)

    def fail_if_network_is_used(*args, **kwargs):
        raise AssertionError("missing credential should fail before network access")

    monkeypatch.setattr(
        "title_localization_lab.adapters.urllib.request.urlopen",
        fail_if_network_is_used,
    )

    with pytest.raises(ProviderError) as error:
        run_pipeline(
            project_root / "data/examples/sample_title_case.json",
            project_root / "configs/title_selection.deepseek.json",
            tmp_path,
            adapter_name="openai-compatible",
        )

    error_payload = read_json(tmp_path / "run_error.json")
    serialized_error = json.dumps(error_payload, ensure_ascii=False)
    assert error.value.code == "PROVIDER_CREDENTIAL_MISSING"
    assert error_payload["code"] == "PROVIDER_CREDENTIAL_MISSING"
    assert error_payload["details"]["environment_variable"] == "DEEPSEEK_API_KEY"
    assert sentinel_key not in serialized_error


def test_provider_adapter_requires_environment_credential(
    pipeline_config,
    monkeypatch,
) -> None:
    monkeypatch.delenv(pipeline_config.provider["api_key_env"], raising=False)
    adapter = OpenAICompatibleAdapter(pipeline_config.provider)
    with pytest.raises(ProviderError) as error:
        adapter._request_json("test")
    assert error.value.code == "PROVIDER_CREDENTIAL_MISSING"
