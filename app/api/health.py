"""Liveness and readiness routes."""

from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from ..config.pipeline_config import load_config
from ..domain.errors import LabError
from ..llm.adapters import validate_openai_compatible_availability

router = APIRouter(tags=["health"])


@router.get("/healthz")
@router.get("/health")
def healthz() -> dict[str, str]:
    """Return process liveness for load balancers and compatibility clients."""

    return {"status": "ok"}


@router.get("/readyz")
def readyz(request: Request):
    """Confirm that the configured OpenAI-compatible model is locally usable."""

    settings = request.app.state.settings
    try:
        config = load_config(settings.pipeline_config_path)
        validate_openai_compatible_availability(config.provider)
    except LabError:
        return JSONResponse(status_code=503, content={"status": "not_ready"})
    return {"status": "ready"}
