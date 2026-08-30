"""Deterministic and opt-in OpenAI-compatible model adapters."""

from __future__ import annotations

import hashlib
import json
import logging
import os
import re
import urllib.error
import urllib.request
from decimal import Decimal
from typing import Any

_logger = logging.getLogger(__name__)
_DEEPSEEK_SCORING_MAX_TOKENS = 16000

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
        "Divine Sign-In",
        "The Check-In Path",
        "Sign-In of the Divine",
        "A God-Tier Check-In",
        "The Divine Check-In Way",
        "Check-In to Divinity",
        "The Sign-In Ascension",
        "Divine System Check-In",
    ),
    "synopsis": (
        "Banished, Then Blessed",
        "The Exile's Hidden System",
        "Check In to Rise Again",
        "From Outcast to Overlord",
        "A Banished Disciple's Return",
        "The System Behind My Exile",
    ),
    "market_localized": (
        "Exiled with the Ultimate System",
        "Every Check-In Makes Me Stronger",
        "My Comeback Starts with a Sign-In",
        "Leveling Up After the Sect Cast Me Out",
        "The Banished Disciple's System",
        "My System-Fueled Return",
    ),
}


def _provider_fields(provider_config: dict[str, Any]) -> tuple[str, str, str]:
    model_id = str(provider_config.get("model", "")).strip()
    base_url = str(provider_config.get("base_url", "")).rstrip("/")
    api_key_env = str(provider_config.get("api_key_env", "LLM_API_KEY")).strip()
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
                    rationale=f"确定性{score}分",
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
        configured_max_tokens = provider_config.get("max_tokens")
        self.max_tokens = (
            int(configured_max_tokens) if configured_max_tokens is not None else None
        )

    @staticmethod
    def _extract_json(content: str, response_id: str | None = None) -> dict[str, Any]:
        """Parse the first valid JSON object from LLM output.

        Handles: markdown code fences, leading/trailing text, BOM,
        trailing commas, and other common LLM formatting quirks.
        """
        # Strip BOM and surrounding whitespace
        text = content.lstrip("﻿").strip()

        # 1. Direct parse — works when the model returns clean JSON
        try:
            value = json.loads(text)
            if isinstance(value, dict):
                return value
        except json.JSONDecodeError:
            pass

        # 2. Strip markdown code fences (```json ... ``` or ``` ... ```)
        stripped = re.sub(r"^```(?:json)?\s*\n?", "", text)
        stripped = re.sub(r"\n?```\s*$", "", stripped).strip()
        try:
            value = json.loads(stripped)
            if isinstance(value, dict):
                return value
        except json.JSONDecodeError:
            pass

        # 3. Extract content between the first { and the last }
        start = text.find("{")
        end = text.rfind("}")
        if start != -1 and end > start:
            fragment = text[start : end + 1]
            try:
                value = json.loads(fragment)
                if isinstance(value, dict):
                    return value
            except json.JSONDecodeError:
                # 4. Remove trailing commas before } or ] (common LLM artifact)
                cleaned = re.sub(r",\s*([}\]])", r"\1", fragment)
                try:
                    value = json.loads(cleaned)
                    if isinstance(value, dict):
                        _logger.warning(
                            "json_recovered_by_trailing_comma_removal "
                            "response_id=%s original_len=%d",
                            response_id,
                            len(text),
                        )
                        return value
                except json.JSONDecodeError:
                    pass

        # 5. Combine: code-fence strip + brace extraction + trailing comma fix
        if start != -1 and end > start:
            combined = re.sub(r",\s*([}\]])", r"\1", stripped[start : end + 1])
            try:
                value = json.loads(combined)
                if isinstance(value, dict):
                    _logger.warning(
                        "json_recovered_by_combined_fix response_id=%s", response_id
                    )
                    return value
            except json.JSONDecodeError:
                pass

        raise ProviderError(
            "供应商响应内容无法解析为 JSON 对象。",
            code="PROVIDER_RESPONSE_INVALID",
            details={
                "response_id": response_id,
                "content_preview": text[:500] if len(text) > 500 else text,
            },
        )

    def _request_json(
        self,
        prompt: str,
        *,
        max_tokens: int | None = None,
    ) -> tuple[dict[str, Any], dict[str, Any]]:
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
        if max_tokens is not None:
            payload["max_tokens"] = max_tokens
        if self.model_id.lower().startswith("deepseek-"):
            payload["thinking"] = {"type": "disabled"}
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
            choice = envelope["choices"][0]
            message = choice["message"]
            content = message["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise ProviderError(
                "供应商响应不包含有效的结构化内容。",
                code="PROVIDER_RESPONSE_INVALID",
                details={"response_id": envelope.get("id")},
            ) from exc
        finish_reason = choice.get("finish_reason")
        usage = envelope.get("usage")
        reasoning_content = message.get("reasoning_content")
        reasoning_content_present = isinstance(reasoning_content, str) and bool(
            reasoning_content.strip()
        )
        content_is_string = isinstance(content, str)
        content_empty = not content_is_string or not content.strip()
        _logger.info(
            "provider_completion_received response_id=%s model_id=%s finish_reason=%s "
            "usage=%s reasoning_content_present=%s content_length=%s content_empty=%s",
            envelope.get("id"),
            self.model_id,
            finish_reason,
            usage,
            reasoning_content_present,
            len(content) if content_is_string else 0,
            content_empty,
        )
        if not content_is_string:
            raise ProviderError(
                "供应商响应不包含字符串结构化内容。",
                code="PROVIDER_RESPONSE_INVALID",
                details={"response_id": envelope.get("id"), "finish_reason": finish_reason},
            )
        if content_empty:
            raise ProviderError(
                "供应商返回了空的结构化内容。",
                code="PROVIDER_RESPONSE_EMPTY",
                details={
                    "response_id": envelope.get("id"),
                    "finish_reason": finish_reason,
                    "usage": usage,
                },
            )
        if finish_reason == "length":
            raise ProviderError(
                "供应商响应因 token 上限被截断，JSON 不完整。",
                code="PROVIDER_RESPONSE_TRUNCATED",
                details={
                    "response_id": envelope.get("id"),
                    "usage": usage,
                    "content_length": len(content),
                },
            )
        value = self._extract_json(content, envelope.get("id"))
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
        max_tokens = None
        if self.model_id.lower().startswith("deepseek-"):
            max_tokens = self.max_tokens or _DEEPSEEK_SCORING_MAX_TOKENS
        value, metadata = self._request_json(request.prompt, max_tokens=max_tokens)
        raw_scores = value.get("scores")
        if not isinstance(raw_scores, list):
            for alt_key in ("evaluations", "results", "candidates"):
                alt = value.get(alt_key)
                if isinstance(alt, list):
                    raw_scores = alt
                    break
        if not isinstance(raw_scores, list):
            top_keys = sorted(value.keys())
            scores_type = type(raw_scores).__name__
            sample = str(raw_scores)[:200] if raw_scores is not None else "null"
            raise ProviderError(
                "评分响应缺少 scores 数组。",
                code="PROVIDER_SCORING_SHAPE_INVALID",
                details={
                    "top_keys": top_keys,
                    "scores_type": scores_type,
                    "scores_sample": sample,
                },
            )
        try:
            scores = tuple(self._parse_candidate_score(item) for item in raw_scores)
        except (KeyError, TypeError, ValueError) as exc:
            first_item_keys = sorted(raw_scores[0].keys()) if raw_scores else []
            raise ProviderError(
                "评分响应结构无效。",
                code="PROVIDER_SCORING_SHAPE_INVALID",
                details={
                    "error": str(exc),
                    "score_count": len(raw_scores),
                    "first_item_keys": first_item_keys,
                },
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
