from __future__ import annotations

import json
import logging
from dataclasses import replace

from app.config.pipeline_config import load_config
from app.domain.errors import ProviderError
from app.llm.adapters import DeterministicAdapter
from app.main import create_app
from app.pipeline.orchestration import run_pipeline_for_source
from app.pipeline.scoring import ModelViolation, ScoringResponse
from app.utils.logging import RunLogContext
from fastapi.testclient import TestClient


def _request_payload(project_root) -> dict[str, object]:
    source = json.loads(
        (project_root / "data/examples/sample_title_case.json").read_text(encoding="utf-8-sig")
    )
    return {"source": source}


def _runner(project_root, adapter=None):
    config = load_config(project_root / "configs/title_selection.default.json")
    resolved_adapter = adapter or DeterministicAdapter()

    def run_request(request, run_context: RunLogContext | None):
        return run_pipeline_for_source(
            request.source.to_source_record(),
            config,
            model_adapter=resolved_adapter,
            run_context=run_context,
        )

    return run_request


class AllIneligibleAdapter(DeterministicAdapter):
    def score(self, request):
        response = super().score(request)
        return ScoringResponse(
            scores=tuple(
                replace(
                    score,
                    violations=(
                        ModelViolation(
                            code="SEMANTIC_MISMATCH",
                            severity="critical",
                            rationale="test violation",
                        ),
                    ),
                )
                for score in response.scores
            ),
            model_id=response.model_id,
            provider_metadata=response.provider_metadata,
        )


class FailingAdapter:
    model_id = "failing-model"

    def generate(self, _request):
        raise ProviderError("provider unavailable", code="PROVIDER_REQUEST_FAILED")


def test_healthz_reports_ready() -> None:
    response = TestClient(create_app()).get("/healthz")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_readiness_requires_configured_model(monkeypatch) -> None:
    monkeypatch.delenv("LLM_API_KEY", raising=False)
    client = TestClient(create_app())

    assert client.get("/readyz").status_code == 503

    monkeypatch.setenv("LLM_API_KEY", "test-key")
    assert client.get("/readyz").json() == {"status": "ready"}


def test_service_routes_report_metadata_and_request_id() -> None:
    client = TestClient(create_app())

    root_response = client.get("/", headers={"X-Request-ID": "request-123"})
    health_response = client.get("/health")

    assert root_response.status_code == 200
    assert root_response.json()["docs"] == "/docs"
    assert root_response.headers["X-Request-ID"] == "request-123"
    assert health_response.json() == {"status": "ok"}


def test_localization_api_returns_compact_model_result(project_root, caplog) -> None:
    caplog.set_level(logging.INFO)
    response = TestClient(create_app(run_request=_runner(project_root))).post(
        "/v1/title-localizations",
        json=_request_payload(project_root),
        headers={"X-Request-ID": "request-logs-123"},
    )

    body = response.json()
    assert response.status_code == 200
    assert set(body) == {"selected", "unselected_titles"}
    assert set(body["selected"]) == {"candidate_id", "title", "score"}
    assert isinstance(body["selected"]["score"], float)
    assert len(body["unselected_titles"]) == 11
    assert "candidate_set" not in body
    assert "ranking_result" not in body
    assert "report" not in body
    assert response.headers["X-Request-ID"] == "request-logs-123"

    messages = "\n".join(record.getMessage() for record in caplog.records)
    assert messages.count("model_call_started request_id=request-logs-123 stage=generation") == 3
    assert messages.count("model_call_completed request_id=request-logs-123 stage=generation") == 3
    assert "model_call_started request_id=request-logs-123 stage=scoring" in messages
    assert "model_call_completed request_id=request-logs-123 stage=scoring" in messages
    assert "selection_completed request_id=request-logs-123" in messages
    assert "LLM_API_KEY" not in messages
    assert "Authorization" not in messages
    assert _request_payload(project_root)["source"]["synopsis"] not in messages


def test_localization_api_rejects_adapter_and_unknown_fields(project_root) -> None:
    payload = _request_payload(project_root)
    payload["adapter"] = "deterministic"

    response = TestClient(create_app(run_request=_runner(project_root))).post(
        "/v1/title-localizations", json=payload
    )

    assert response.status_code == 422
    body = response.json()
    assert body["error"]["code"] == "REQUEST_VALIDATION_ERROR"
    assert "selected" not in body
    assert "unselected_titles" not in body


def test_localization_api_rejects_missing_genre_zh(project_root) -> None:
    payload = _request_payload(project_root)
    source = payload["source"]
    assert isinstance(source, dict)
    source.pop("genre_zh")

    response = TestClient(create_app(run_request=_runner(project_root))).post(
        "/v1/title-localizations", json=payload
    )

    assert response.status_code == 422
    body = response.json()
    assert body["error"]["code"] == "REQUEST_VALIDATION_ERROR"
    assert "genre_zh" in json.dumps(body, ensure_ascii=False)
    assert "input" not in json.dumps(body, ensure_ascii=False)
    assert response.headers["X-Request-ID"]


def test_localization_api_returns_no_data_when_model_credential_is_missing(project_root, monkeypatch) -> None:
    monkeypatch.delenv("LLM_API_KEY", raising=False)
    response = TestClient(create_app()).post(
        "/v1/title-localizations", json=_request_payload(project_root)
    )

    assert response.status_code == 502
    body = response.json()
    assert body["error"]["code"] == "PROVIDER_CREDENTIAL_MISSING"
    assert "selected" not in body
    assert "unselected_titles" not in body
    assert "api_key" not in json.dumps(body, ensure_ascii=False).lower()


def test_localization_api_returns_no_data_when_provider_fails(project_root, monkeypatch) -> None:
    monkeypatch.setenv("LLM_API_KEY", "test-key")
    monkeypatch.setattr("app.pipeline.service.create_adapter", lambda *_: FailingAdapter())

    response = TestClient(create_app()).post(
        "/v1/title-localizations", json=_request_payload(project_root)
    )

    assert response.status_code == 502
    body = response.json()
    assert body["error"]["code"] == "PROVIDER_REQUEST_FAILED"
    assert "selected" not in body
    assert "unselected_titles" not in body


def test_localization_api_rejects_a_run_without_an_eligible_winner(project_root) -> None:
    response = TestClient(
        create_app(run_request=_runner(project_root, AllIneligibleAdapter()))
    ).post("/v1/title-localizations", json=_request_payload(project_root))

    assert response.status_code == 422
    body = response.json()
    assert body["error"]["code"] == "NO_ELIGIBLE_WINNER"
    assert "selected" not in body
    assert "unselected_titles" not in body
