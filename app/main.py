"""FastAPI application factory and process-level HTTP concerns."""

from __future__ import annotations

import logging
import uuid
from collections.abc import Callable
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from .api.errors import error_payload, validation_error_details
from .api.routes import health_router, title_localizations_router
from .config.settings import Settings, get_settings
from .domain.errors import LabError, ProviderError
from .domain.http_models import LocalizationRequest
from .pipeline.orchestration import InMemoryOutcome
from .pipeline.service import build_localization_runner
from .utils.logging import configure_logging

logger = logging.getLogger(__name__)


def _request_id(request: Request) -> str:
    value = (request.headers.get("X-Request-ID") or "").strip()
    return value if 0 < len(value) <= 200 else str(uuid.uuid4())


def create_app(
    run_request: Callable[[LocalizationRequest], InMemoryOutcome] | None = None,
    settings: Settings | None = None,
) -> FastAPI:
    """Create a configured API app; injectable dependencies keep HTTP tests isolated."""

    resolved_settings = settings or get_settings()
    configure_logging(resolved_settings.log_level)

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        logger.info("service_starting environment=%s", resolved_settings.environment)
        yield
        logger.info("service_stopped")

    app = FastAPI(
        title=resolved_settings.app_name,
        version=resolved_settings.app_version,
        description="Generate and rank English titles for Chinese web novels.",
        lifespan=lifespan,
    )
    app.state.settings = resolved_settings
    app.state.run_localization = run_request or build_localization_runner(resolved_settings)

    if resolved_settings.cors_origins:
        allow_credentials = "*" not in resolved_settings.cors_origins
        app.add_middleware(
            CORSMiddleware,
            allow_origins=list(resolved_settings.cors_origins),
            allow_credentials=allow_credentials,
            allow_methods=["GET", "POST"],
            allow_headers=["Content-Type", "X-Request-ID"],
        )

    @app.middleware("http")
    async def add_request_context(request: Request, call_next):
        request_id = _request_id(request)
        request.state.request_id = request_id
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        return response

    @app.exception_handler(RequestValidationError)
    async def handle_request_validation_error(
        _: Request, exc: RequestValidationError
    ) -> JSONResponse:
        return JSONResponse(
            status_code=422,
            content=error_payload(
                "REQUEST_VALIDATION_ERROR",
                "Invalid request",
                validation_error_details(exc.errors()),
            ),
        )

    @app.exception_handler(LabError)
    async def handle_lab_error(_: Request, exc: LabError) -> JSONResponse:
        if isinstance(exc, ProviderError):
            return JSONResponse(
                status_code=502,
                content=error_payload(exc.code, "Provider request failed"),
            )
        return JSONResponse(
            status_code=422,
            content=error_payload(exc.code, exc.message, exc.details),
        )

    @app.exception_handler(Exception)
    async def handle_unexpected_error(request: Request, exc: Exception) -> JSONResponse:
        logger.exception("unhandled_request_error request_id=%s", request.state.request_id)
        return JSONResponse(
            status_code=500,
            content=error_payload("INTERNAL_SERVER_ERROR", "Internal server error"),
        )

    @app.get("/", tags=["service"])
    def root() -> dict[str, str]:
        return {
            "service": resolved_settings.app_name,
            "version": resolved_settings.app_version,
            "status": "running",
            "docs": "/docs",
        }

    app.include_router(health_router)
    app.include_router(title_localizations_router)
    return app


app = create_app()
