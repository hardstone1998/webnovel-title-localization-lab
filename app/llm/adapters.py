"""Deterministic and opt-in OpenAI-compatible model adapters."""

from __future__ import annotations

import hashlib
import json
import os
import urllib.error
import urllib.request
from decimal import Decimal
from typing import Any

from ..config.pipeline_config import PipelineConfig
from ..domain.contracts import DIMENSIONS
from ..domain.errors import ProviderError
from ..pipeline.generation import GenerationRequest, GenerationResponse
from ..pipeline.scoring import (
    ModelCandidateScore,
    ModelDimensionScore,
    ModelViolation,
    ScoringRequest,
    ScoringResponse,
)

_DETERMINISTIC_TITLES = {
    "source_title": (
        "The Divine Check-In System",
        "Awakening the God-Tier Sign-In",
        "My Supreme Sign-In Power",
        "Starting with a Divine Check-In",
    ),
    "synopsis": (
        "Banished, Then Blessed",
        "The Exile's Hidden System",
        "Check In to Rise Again",
        "From Outcast to Overlord",
    ),
    "market_localized": (
        "Exiled with the Ultimate System",
        "Every Check-In Makes Me Stronger",
        "My Comeback Starts with a Sign-In",
        "Leveling Up After the Sect Cast Me Out",
    ),
}


def _provider_fields(provider_config: dict[str, Any]) -> tuple[str, str, str]:
    model_id = str(provider_config.get("model", "")).strip()
    base_url = str(provider_config.get("base_url", "")).rstrip("/")
    api_key_env = str(provider_config.get("api_key_env", "TITLE_LOCALIZATION_API_KEY")).strip()
    if not model_id or not base_url or not api_key_env:
        raise ProviderError(
            "供应商配置缺少 model、base_url 或 api_key_env。",
            code="INVALID_PROVIDER_CONFIGURATION",
        )
    return model_id, base_url, api_key_env


def validate_openai_compatible_availability(provider_config: dict[str, Any]) -> None:
    """Validate local provider prerequisites without sending a network request."""

    _, _, api_key_env = _provider_fields(provider_config)
    if not os.environ.get(api_key_env, "").strip():
        raise ProviderError(
            f"环境变量 {api_key_env} 未设置。",
            code="PROVIDER_CREDENTIAL_MISSING",
            details={"environment_variable": api_key_env},
        )


class DeterministicAdapter:
    """Offline adapter with stable synthetic outputs."""

    model_id = "deterministic-synthetic-v1"

    def generate(self, request: GenerationRequest) -> GenerationResponse:
        excluded = {title.casefold() for title in request.excluded_titles}
        titles = tuple(
            title
            for title in _DETERMINISTIC_TITLES[request.strategy]
            if title.casefold() not in excluded
        )[: request.count]
        return GenerationResponse(
            titles=titles,
            model_id=self.model_id,
            provider_metadata={"adapter": "deterministic", "network": False},
        )

    def score(self, request: ScoringRequest) -> ScoringResponse:
        scores: list[ModelCandidateScore] = []
        for candidate_id, title in request.candidates:
            digest = hashlib.sha256(title.encode("utf-8")).digest()
            dimensions: dict[str, ModelDimensionScore] = {}
            total = Decimal(0)
            for index, dimension in enumerate(DIMENSIONS):
                score = 6 + digest[index] % 5
                contribution = (
                    Decimal(score) * Decimal(request.weights[dimension]) / Decimal(10)
                ).quantize(Decimal("0.01"))
                total += contribution
                dimensions[dimension] = ModelDimensionScore(
                    score=score,
                    rationale=f"确定性测试评分：{dimension}={score}。",
                    weighted_contribution=contribution,
                )
            scores.append(
                ModelCandidateScore(
                    candidate_id=candidate_id,
                    title=title,
                    dimensions=dimensions,
                    violations=(),
                    weighted_total=total.quantize(Decimal("0.01")),
                )
            )
        return ScoringResponse(
            scores=tuple(scores),
            model_id=self.model_id,
            provider_metadata={"adapter": "deterministic", "network": False},
        )


class OpenAICompatibleAdapter:
    """Minimal JSON-output adapter for an explicitly configured compatible endpoint."""

    def __init__(self, provider_config: dict[str, Any]) -> None:
        self.model_id, self.base_url, self.api_key_env = _provider_fields(provider_config)
        self.timeout_seconds = int(provider_config.get("timeout_seconds", 60))

    def _request_json(self, prompt: str) -> tuple[dict[str, Any], dict[str, Any]]:
        api_key = os.environ.get(self.api_key_env)
        if not api_key:
            raise ProviderError(
                f"环境变量 {self.api_key_env} 未设置。",
                code="PROVIDER_CREDENTIAL_MISSING",
                details={"environment_variable": self.api_key_env},
            )
        payload = {
            "model": self.model_id,
            "messages": [{"role": "user", "content": prompt}],
            "response_format": {"type": "json_object"},
        }
        request = urllib.request.Request(
            f"{self.base_url}/chat/completions",
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout_seconds) as response:
                envelope = json.loads(response.read().decode("utf-8"))
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, KeyError) as exc:
            raise ProviderError(
                "供应商请求失败或返回了无效 JSON。",
                code="PROVIDER_REQUEST_FAILED",
                details={"error": str(exc), "base_url": self.base_url},
            ) from exc
        try:
            content = envelope["choices"][0]["message"]["content"]
            value = json.loads(content)
        except (KeyError, IndexError, TypeError, json.JSONDecodeError) as exc:
            raise ProviderError(
                "供应商响应不包含有效的结构化内容。",
                code="PROVIDER_RESPONSE_INVALID",
                details={"response_id": envelope.get("id")},
            ) from exc
        if not isinstance(value, dict):
            raise ProviderError(
                "供应商结构化内容的根节点必须是对象。",
                code="PROVIDER_RESPONSE_INVALID",
            )
        metadata = {
            "adapter": "openai-compatible",
            "response_id": envelope.get("id"),
            "base_url": self.base_url,
        }
        return value, metadata

    def generate(self, request: GenerationRequest) -> GenerationResponse:
        value, metadata = self._request_json(request.prompt)
        titles = value.get("titles")
        if not isinstance(titles, list):
            raise ProviderError(
                "生成响应缺少 titles 数组。",
                code="PROVIDER_GENERATION_SHAPE_INVALID",
            )
        return GenerationResponse(
            titles=tuple(str(item) for item in titles),
            model_id=self.model_id,
            provider_metadata=metadata,
        )

    def score(self, request: ScoringRequest) -> ScoringResponse:
        value, metadata = self._request_json(request.prompt)
        raw_scores = value.get("scores")
        if not isinstance(raw_scores, list):
            raise ProviderError(
                "评分响应缺少 scores 数组。",
                code="PROVIDER_SCORING_SHAPE_INVALID",
            )
        try:
            scores = tuple(self._parse_candidate_score(item) for item in raw_scores)
        except (KeyError, TypeError, ValueError) as exc:
            raise ProviderError(
                "评分响应结构无效。",
                code="PROVIDER_SCORING_SHAPE_INVALID",
                details={"error": str(exc)},
            ) from exc
        return ScoringResponse(
            scores=scores,
            model_id=self.model_id,
            provider_metadata=metadata,
        )

    @staticmethod
    def _parse_candidate_score(item: dict[str, Any]) -> ModelCandidateScore:
        dimensions = {
            name: ModelDimensionScore(
                score=value["score"],
                rationale=str(value["rationale"]),
                weighted_contribution=Decimal(str(value["weighted_contribution"])),
            )
            for name, value in item["dimensions"].items()
        }
        violations = tuple(
            ModelViolation(
                code=str(value["code"]),
                severity=str(value["severity"]),
                rationale=str(value["rationale"]),
                evidence_field=str(value.get("evidence_field", "")),
            )
            for value in item.get("violations", [])
        )
        return ModelCandidateScore(
            candidate_id=str(item["candidate_id"]),
            title=str(item["title"]),
            dimensions=dimensions,
            violations=violations,
            weighted_total=Decimal(str(item["weighted_total"])),
        )


def create_adapter(name: str, config: PipelineConfig) -> Any:
    if name == "deterministic":
        return DeterministicAdapter()
    if name == "openai-compatible":
        return OpenAICompatibleAdapter(config.provider)
    raise ProviderError(
        "未知适配器。",
        code="UNKNOWN_ADAPTER",
        details={"adapter": name},
    )
