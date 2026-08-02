from __future__ import annotations

import json

from app.main import create_app
from fastapi.testclient import TestClient


def _request_payload(project_root) -> dict[str, object]:
    source = json.loads(
        (project_root / "data/examples/sample_title_case.json").read_text(encoding="utf-8-sig")
    )
    return {"source": source, "adapter": "deterministic"}


def test_healthz_reports_ready() -> None:
    response = TestClient(create_app()).get("/healthz")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_service_routes_report_metadata_and_request_id() -> None:
    client = TestClient(create_app())

    root_response = client.get("/", headers={"X-Request-ID": "request-123"})
    health_response = client.get("/health")
    ready_response = client.get("/readyz")

    assert root_response.status_code == 200
    assert root_response.json()["docs"] == "/docs"
    assert root_response.headers["X-Request-ID"] == "request-123"
    assert health_response.json() == {"status": "ok"}
    assert ready_response.json() == {"status": "ready"}


def test_localization_api_runs_the_deterministic_pipeline(project_root) -> None:
    response = TestClient(create_app()).post(
        "/v1/title-localizations",
        json=_request_payload(project_root),
    )

    body = response.json()
    assert response.status_code == 200
    assert len(body["candidate_set"]["candidates"]) == 12
    assert len(body["ranking_result"]["scores"]) == 12
    assert body["ranking_result"]["winner_candidate_id"]
    assert body["report"]
    assert response.headers["X-Request-ID"]


def test_localization_api_rejects_missing_genre_zh(project_root) -> None:
    payload = _request_payload(project_root)
    source = payload["source"]
    assert isinstance(source, dict)
    source.pop("genre_zh")

    response = TestClient(create_app()).post("/v1/title-localizations", json=payload)

    assert response.status_code == 422
    body = response.json()
    assert body["error"]["code"] == "REQUEST_VALIDATION_ERROR"
    assert "genre_zh" in json.dumps(body, ensure_ascii=False)
    assert "input" not in json.dumps(body, ensure_ascii=False)
    assert response.headers["X-Request-ID"]


def test_localization_api_returns_safe_provider_error(project_root, monkeypatch) -> None:
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    payload = _request_payload(project_root)
    payload.update({"config_profile": "deepseek", "adapter": "openai-compatible"})

    response = TestClient(create_app()).post("/v1/title-localizations", json=payload)

    assert response.status_code == 502
    body = response.json()
    assert body["error"]["code"] == "PROVIDER_CREDENTIAL_MISSING"
    assert "api_key" not in json.dumps(body, ensure_ascii=False).lower()
