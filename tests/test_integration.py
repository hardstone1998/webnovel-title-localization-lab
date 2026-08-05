from __future__ import annotations

import json
import logging

import pytest
from app.cli import main
from app.config.pipeline_config import load_config
from app.domain.contracts import SourceRecord
from app.domain.errors import ProviderError
from app.llm.adapters import DeterministicAdapter, OpenAICompatibleAdapter
from app.pipeline.orchestration import run_pipeline, run_pipeline_for_source
from app.pipeline.scoring import ScoringRequest
from app.utils.artifacts import atomic_write_json, read_json
from jsonschema import Draft202012Validator


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


def test_in_memory_pipeline_matches_the_deterministic_candidate_contract(project_root) -> None:
    source = SourceRecord.from_dict(
        read_json(project_root / "data/examples/sample_title_case.json")
    )
    config = load_config(project_root / "configs/title_selection.default.json")

    outcome = run_pipeline_for_source(
        source,
        config,
        model_adapter=DeterministicAdapter(),
    )

    assert len(outcome.candidate_set.candidates) == 12
    assert len(outcome.ranking.scores) == 12
    assert outcome.ranking.winner_candidate_id
    assert outcome.report


def test_cli_runs_offline(project_root, tmp_path, capsys, monkeypatch) -> None:
    monkeypatch.delenv("LLM_API_KEY", raising=False)

    def fail_if_network_is_used(*args, **kwargs):
        raise AssertionError("deterministic adapter attempted network access")

    monkeypatch.setattr(
        "app.llm.adapters.urllib.request.urlopen",
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


def test_openai_compatible_provider_config_loads_without_a_credential_value(
    project_root,
    monkeypatch,
) -> None:
    monkeypatch.setenv("LLM_MODEL", "gpt-4.1-mini")
    monkeypatch.setenv("LLM_BASE_URL", "https://api.openai.com/v1")
    monkeypatch.setenv("LLM_TIMEOUT_SECONDS", "60")
    monkeypatch.setenv("LLM_MAX_TOKENS", "16000")
    config_path = project_root / "configs/title_selection.default.json"
    raw_config = read_json(config_path)
    config = load_config(config_path)

    assert config.provider == {
        "model": "gpt-4.1-mini",
        "base_url": "https://api.openai.com/v1",
        "api_key_env": "LLM_API_KEY",
        "timeout_seconds": 60,
        "max_tokens": 16000,
    }
    assert "api_key" not in raw_config["provider"]
    assert "LLM_API_KEY" in config_path.read_text(encoding="utf-8")


def test_openai_compatible_request_uses_json_contract(
    project_root,
    tmp_path,
    monkeypatch,
) -> None:
    sentinel_key = "test-only-provider-secret"
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

    monkeypatch.setenv("LLM_MODEL", "test-model")
    monkeypatch.setenv("LLM_BASE_URL", "https://llm.example/v1")
    monkeypatch.setenv("LLM_TIMEOUT_SECONDS", "45")
    monkeypatch.setenv("LLM_API_KEY", sentinel_key)
    config = load_config(project_root / "configs/title_selection.default.json")
    monkeypatch.setattr(
        "app.llm.adapters.urllib.request.urlopen",
        fake_urlopen,
    )

    value, metadata = OpenAICompatibleAdapter(config.provider)._request_json(
        '只返回 JSON：{"titles":["..."]}。'
    )

    request = captured["request"]
    body = json.loads(request.data.decode("utf-8"))
    assert request.full_url == "https://llm.example/v1/chat/completions"
    assert request.get_header("Authorization") == f"Bearer {sentinel_key}"
    assert body["model"] == "test-model"
    assert "json" in body["messages"][0]["content"].lower()
    assert body["response_format"] == {"type": "json_object"}
    assert "max_tokens" not in body
    assert captured["timeout"] == 45
    assert value == {"titles": ["A Tested Title"]}
    assert metadata == {
        "adapter": "openai-compatible",
        "response_id": "response-test",
        "base_url": "https://llm.example/v1",
    }

    representative_artifact = atomic_write_json(
        tmp_path / "provider_artifact.json",
        {
            "public_config": config.public_dict(),
            "provider_metadata": metadata,
        },
    )
    assert sentinel_key not in representative_artifact.read_text(encoding="utf-8")


def test_deepseek_scoring_request_uses_default_output_budget(monkeypatch) -> None:
    captured: dict[str, object] = {}
    envelope = {
        "id": "response-score",
        "choices": [{"message": {"content": json.dumps({"scores": []})}}],
    }

    def fake_urlopen(request, timeout):
        captured["request"] = request
        return StubHTTPResponse(envelope)

    monkeypatch.setenv("LLM_API_KEY", "test-only-provider-secret")
    monkeypatch.setattr("app.llm.adapters.urllib.request.urlopen", fake_urlopen)
    adapter = OpenAICompatibleAdapter(
        {
            "model": "deepseek-v4-flash",
            "base_url": "https://llm.example/v1",
            "api_key_env": "LLM_API_KEY",
        }
    )

    adapter.score(
        ScoringRequest(
            prompt='return {"scores": []}',
            candidates=(),
            weights={},
            permutation_seed=0,
        )
    )

    body = json.loads(captured["request"].data.decode("utf-8"))
    assert body["max_tokens"] == 16000


def test_deepseek_scoring_request_honors_explicit_output_budget(monkeypatch) -> None:
    captured: dict[str, object] = {}
    envelope = {
        "id": "response-score-custom",
        "choices": [{"message": {"content": json.dumps({"scores": []})}}],
    }

    def fake_urlopen(request, timeout):
        captured["request"] = request
        return StubHTTPResponse(envelope)

    monkeypatch.setenv("LLM_API_KEY", "test-only-provider-secret")
    monkeypatch.setattr("app.llm.adapters.urllib.request.urlopen", fake_urlopen)
    adapter = OpenAICompatibleAdapter(
        {
            "model": "deepseek-v4-flash",
            "base_url": "https://llm.example/v1",
            "api_key_env": "LLM_API_KEY",
            "max_tokens": 24000,
        }
    )

    adapter.score(
        ScoringRequest(
            prompt='return {"scores": []}',
            candidates=(),
            weights={},
            permutation_seed=0,
        )
    )

    body = json.loads(captured["request"].data.decode("utf-8"))
    assert body["max_tokens"] == 24000


def test_empty_provider_content_has_safe_completion_diagnostics(monkeypatch, caplog) -> None:
    envelope = {
        "id": "response-empty",
        "usage": {"completion_tokens": 17, "prompt_tokens": 31},
        "choices": [
            {
                "finish_reason": "length",
                "message": {"content": "", "reasoning_content": "private chain of thought"},
            }
        ],
    }

    monkeypatch.setenv("LLM_API_KEY", "test-only-provider-secret")
    monkeypatch.setattr(
        "app.llm.adapters.urllib.request.urlopen",
        lambda request, timeout: StubHTTPResponse(envelope),
    )
    adapter = OpenAICompatibleAdapter(
        {
            "model": "deepseek-v4-flash",
            "base_url": "https://llm.example/v1",
            "api_key_env": "LLM_API_KEY",
        }
    )

    caplog.set_level(logging.INFO, logger="app.llm.adapters")
    with pytest.raises(ProviderError) as error:
        adapter._request_json('return {"scores": []}')

    assert error.value.code == "PROVIDER_RESPONSE_EMPTY"
    assert error.value.details == {
        "response_id": "response-empty",
        "finish_reason": "length",
        "usage": {"completion_tokens": 17, "prompt_tokens": 31},
    }
    messages = "\n".join(record.getMessage() for record in caplog.records)
    assert "provider_completion_received" in messages
    assert "finish_reason=length" in messages
    assert "reasoning_content_present=True" in messages
    assert "content_empty=True" in messages
    assert "private chain of thought" not in messages


def test_completion_diagnostics_never_log_model_or_reasoning_text(monkeypatch, caplog) -> None:
    envelope = {
        "id": "response-private-content",
        "usage": {"completion_tokens": 12},
        "choices": [
            {
                "finish_reason": "stop",
                "message": {
                    "content": json.dumps({"titles": ["private model title"]}),
                    "reasoning_content": "private chain of thought",
                },
            }
        ],
    }

    monkeypatch.setenv("LLM_API_KEY", "test-only-provider-secret")
    monkeypatch.setattr(
        "app.llm.adapters.urllib.request.urlopen",
        lambda request, timeout: StubHTTPResponse(envelope),
    )
    adapter = OpenAICompatibleAdapter(
        {
            "model": "deepseek-v4-flash",
            "base_url": "https://llm.example/v1",
            "api_key_env": "LLM_API_KEY",
        }
    )

    caplog.set_level(logging.INFO, logger="app.llm.adapters")
    value, _ = adapter._request_json('return {"titles": ["..."]}')

    assert value == {"titles": ["private model title"]}
    messages = "\n".join(record.getMessage() for record in caplog.records)
    assert "reasoning_content_present=True" in messages
    assert "private model title" not in messages
    assert "private chain of thought" not in messages


def test_openai_compatible_missing_credential_writes_safe_error(
    project_root,
    tmp_path,
    monkeypatch,
) -> None:
    sentinel_key = "test-only-provider-secret"
    monkeypatch.delenv("LLM_API_KEY", raising=False)

    def fail_if_network_is_used(*args, **kwargs):
        raise AssertionError("missing credential should fail before network access")

    monkeypatch.setattr(
        "app.llm.adapters.urllib.request.urlopen",
        fail_if_network_is_used,
    )

    with pytest.raises(ProviderError) as error:
        run_pipeline(
            project_root / "data/examples/sample_title_case.json",
            project_root / "configs/title_selection.default.json",
            tmp_path,
            adapter_name="openai-compatible",
        )

    error_payload = read_json(tmp_path / "run_error.json")
    serialized_error = json.dumps(error_payload, ensure_ascii=False)
    assert error.value.code == "PROVIDER_CREDENTIAL_MISSING"
    assert error_payload["code"] == "PROVIDER_CREDENTIAL_MISSING"
    assert error_payload["details"]["environment_variable"] == "LLM_API_KEY"
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
