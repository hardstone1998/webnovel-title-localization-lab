"""Application service that adapts HTTP requests to the core pipeline."""

from __future__ import annotations

import logging
from collections.abc import Callable

from ..config.pipeline_config import PipelineConfig, load_config
from ..config.settings import Settings
from ..domain.http_models import LocalizationRequest
from ..llm.adapters import create_adapter, validate_openai_compatible_availability
from ..utils.logging import RunLogContext
from .orchestration import InMemoryOutcome, run_pipeline_for_source

LocalizationRunner = Callable[[LocalizationRequest, RunLogContext | None], InMemoryOutcome]
logger = logging.getLogger(__name__)


def build_localization_runner(settings: Settings) -> LocalizationRunner:
    """Bind reviewed configuration profiles to an in-memory pipeline runner."""

    def run_request(
        request: LocalizationRequest, run_context: RunLogContext | None = None
    ) -> InMemoryOutcome:
        config: PipelineConfig = load_config(settings.config_profiles[request.config_profile])
        try:
            validate_openai_compatible_availability(config.provider)
        except Exception as exc:
            logger.error(
                "model_call_failed request_id=%s stage=preflight model_id=%s error_code=%s",
                (run_context or RunLogContext()).correlation_id,
                str(config.provider.get("model", "unknown")),
                getattr(exc, "code", "MODEL_CONFIGURATION_FAILED"),
            )
            raise
        adapter = create_adapter("openai-compatible", config)
        return run_pipeline_for_source(
            request.source.to_source_record(),
            config,
            model_adapter=adapter,
            run_context=run_context,
        )

    return run_request
