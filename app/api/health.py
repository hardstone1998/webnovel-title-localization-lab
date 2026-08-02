"""Liveness and readiness routes."""

from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from ..config.pipeline_config import load_config
from ..domain.errors import LabError

router = APIRouter(tags=["health"])


@router.get("/healthz")
@router.get("/health")
def healthz() -> dict[str, str]:
    """Return process liveness for load balancers and compatibility clients."""

    return {"status": "ok"}


@router.get("/readyz")
def readyz(request: Request):
    """Confirm that the default reviewed pipeline configuration can be loaded."""

    settings = request.app.state.settings
    try:
        load_config(settings.default_config_path)
    except LabError:
        return JSONResponse(status_code=503, content={"status": "not_ready"})
    return {"status": "ready"}
