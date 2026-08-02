"""Application service that adapts HTTP requests to the core pipeline."""

from __future__ import annotations

from collections.abc import Callable

from ..config.pipeline_config import PipelineConfig, load_config
from ..config.settings import Settings
from ..domain.http_models import LocalizationRequest
from ..llm.adapters import create_adapter
from .orchestration import InMemoryOutcome, run_pipeline_for_source

LocalizationRunner = Callable[[LocalizationRequest], InMemoryOutcome]


def build_localization_runner(settings: Settings) -> LocalizationRunner:
    """Bind reviewed configuration profiles to an in-memory pipeline runner."""

    def run_request(request: LocalizationRequest) -> InMemoryOutcome:
        config: PipelineConfig = load_config(settings.config_profiles[request.config_profile])
        adapter = create_adapter(request.adapter, config)
        return run_pipeline_for_source(
            request.source.to_source_record(),
            config,
            model_adapter=adapter,
        )

    return run_request
