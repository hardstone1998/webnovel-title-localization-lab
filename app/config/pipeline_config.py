"""Configuration loading and strict validation."""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ..domain.contracts import DIMENSIONS, STRATEGIES
from ..domain.errors import ValidationError
from ..prompts.templates import SUPPORTED_SCORING_PROMPT_VERSIONS
from .settings import load_project_dotenv

_ENV_VALUE = re.compile(r"^\$\{([A-Z][A-Z0-9_]*)(?::-([^}]*))?\}$")
_LEGACY_STRATEGY_COUNTS = {strategy: 4 for strategy in STRATEGIES}
_LEGACY_COVERAGE_SLOTS = {
    strategy: tuple(f"legacy_{ordinal}" for ordinal in range(1, 5))
    for strategy in STRATEGIES
}


@dataclass(frozen=True)
class GenerationConfig:
    max_attempts: int
    prompt_versions: dict[str, str]
    parameters: dict[str, Any]
    target_locale: str
    target_market: str
    strategy_counts: dict[str, int]
    coverage_slots: dict[str, tuple[str, ...]]


@dataclass(frozen=True)
class ScoringConfig:
    max_attempts: int
    rubric_version: str
    weight_version: str
    prompt_version: str
    permutation_seed: int
    weights: dict[str, int]
    dimension_guidance: dict[str, str]
    tie_break_order: tuple[str, ...]


@dataclass(frozen=True)
class PipelineConfig:
    schema_version: str
    generation: GenerationConfig
    scoring: ScoringConfig
    provider: dict[str, Any]

    def public_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "generation": {
                "max_attempts": self.generation.max_attempts,
                "prompt_versions": self.generation.prompt_versions,
                "parameters": self.generation.parameters,
                "target_locale": self.generation.target_locale,
                "target_market": self.generation.target_market,
                "strategy_counts": self.generation.strategy_counts,
                "coverage_slots": {
                    strategy: list(slots)
                    for strategy, slots in self.generation.coverage_slots.items()
                },
            },
            "scoring": {
                "max_attempts": self.scoring.max_attempts,
                "rubric_version": self.scoring.rubric_version,
                "weight_version": self.scoring.weight_version,
                "prompt_version": self.scoring.prompt_version,
                "permutation_seed": self.scoring.permutation_seed,
                "weights": self.scoring.weights,
                "dimension_guidance": self.scoring.dimension_guidance,
                "tie_break_order": list(self.scoring.tie_break_order),
            },
            "provider": {
                key: value
                for key, value in self.provider.items()
                if "key" not in key.lower() and "secret" not in key.lower()
            },
        }


def _positive_int(value: Any, field_name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise ValidationError(
            f"{field_name} 必须是正整数。",
            code="INVALID_CONFIGURATION_VALUE",
            details={"field": field_name, "value": value},
        )
    return value


def parse_config(data: dict[str, Any]) -> PipelineConfig:
    try:
        generation = data["generation"]
        scoring = data["scoring"]
        prompt_versions = generation["prompt_versions"]
        weights = scoring["weights"]
        guidance = scoring["dimension_guidance"]
    except (KeyError, TypeError) as exc:
        raise ValidationError(
            "配置缺少必填字段。",
            code="CONFIG_REQUIRED_FIELD_MISSING",
            details={"field": str(exc)},
        ) from exc

    if set(prompt_versions) != set(STRATEGIES):
        raise ValidationError(
            "生成提示词版本必须覆盖且仅覆盖三种策略。",
            code="INVALID_PROMPT_VERSION_KEYS",
            details={"keys": sorted(prompt_versions)},
        )
    strategy_counts = generation.get("strategy_counts", _LEGACY_STRATEGY_COUNTS)
    coverage_slots = generation.get("coverage_slots", _LEGACY_COVERAGE_SLOTS)
    if not isinstance(strategy_counts, dict) or set(strategy_counts) != set(STRATEGIES):
        raise ValidationError(
            "generation.strategy_counts 必须准确覆盖三种策略。",
            code="INVALID_STRATEGY_COUNT_KEYS",
            details={"keys": sorted(strategy_counts) if isinstance(strategy_counts, dict) else []},
        )
    parsed_strategy_counts = {
        strategy: _positive_int(strategy_counts[strategy], f"generation.strategy_counts.{strategy}")
        for strategy in STRATEGIES
    }
    if sum(parsed_strategy_counts.values()) not in {12, 24}:
        raise ValidationError(
            "generation.strategy_counts 的总和必须为 12 或 24。",
            code="INVALID_STRATEGY_COUNT_TOTAL",
            details={"total": sum(parsed_strategy_counts.values())},
        )
    if not isinstance(coverage_slots, dict) or set(coverage_slots) != set(STRATEGIES):
        raise ValidationError(
            "generation.coverage_slots 必须准确覆盖三种策略。",
            code="INVALID_COVERAGE_SLOT_KEYS",
        )
    parsed_coverage_slots: dict[str, tuple[str, ...]] = {}
    for strategy in STRATEGIES:
        slots = coverage_slots[strategy]
        if not isinstance(slots, (list, tuple)) or len(slots) != parsed_strategy_counts[strategy]:
            raise ValidationError(
                "每种策略的 coverage_slots 数量必须与其配额一致。",
                code="INVALID_COVERAGE_SLOT_COUNT",
                details={"strategy": strategy},
            )
        cleaned_slots = tuple(str(slot).strip() for slot in slots)
        if not all(cleaned_slots) or len(set(cleaned_slots)) != len(cleaned_slots):
            raise ValidationError(
                "coverage_slots 必须为策略内唯一的非空名称。",
                code="INVALID_COVERAGE_SLOT_VALUE",
                details={"strategy": strategy},
            )
        parsed_coverage_slots[strategy] = cleaned_slots
    expected_dimensions = set(DIMENSIONS)
    if set(weights) != expected_dimensions or set(guidance) != expected_dimensions:
        raise ValidationError(
            "评分权重和说明必须准确覆盖八个评分维度。",
            code="INVALID_DIMENSION_KEYS",
            details={
                "weight_keys": sorted(weights),
                "guidance_keys": sorted(guidance),
            },
        )
    for dimension, value in weights.items():
        _positive_int(value, f"scoring.weights.{dimension}")
    if sum(weights.values()) != 100:
        raise ValidationError(
            "八项评分权重总和必须为 100。",
            code="INVALID_WEIGHT_TOTAL",
            details={"total": sum(weights.values())},
        )
    if any(not str(guidance[item]).strip() for item in DIMENSIONS):
        raise ValidationError(
            "每个评分维度都必须提供说明。",
            code="INVALID_DIMENSION_GUIDANCE",
        )
    if str(scoring.get("prompt_version", "")).strip() not in SUPPORTED_SCORING_PROMPT_VERSIONS:
        raise ValidationError(
            "评分提示词版本不受支持。",
            code="UNSUPPORTED_SCORING_PROMPT_VERSION",
            details={
                "prompt_version": scoring.get("prompt_version"),
                "supported": sorted(SUPPORTED_SCORING_PROMPT_VERSIONS),
            },
        )
    required_versions = {
        "schema_version": data.get("schema_version"),
        "scoring.rubric_version": scoring.get("rubric_version"),
        "scoring.weight_version": scoring.get("weight_version"),
        "scoring.prompt_version": scoring.get("prompt_version"),
        "generation.target_locale": generation.get("target_locale"),
        "generation.target_market": generation.get("target_market"),
    }
    empty_versions = [
        key for key, value in required_versions.items() if not str(value or "").strip()
    ]
    if empty_versions:
        raise ValidationError(
            "配置的版本或目标市场字段不得为空。",
            code="EMPTY_CONFIGURATION_FIELD",
            details={"fields": empty_versions},
        )
    expected_ties = (
        "authoritative_total",
        "semantic_fidelity",
        "integrity_safety",
        "natural_english",
        "candidate_id",
    )
    if tuple(scoring.get("tie_break_order", ())) != expected_ties:
        raise ValidationError(
            "同分处理顺序与规格不一致。",
            code="INVALID_TIE_BREAK_ORDER",
            details={"expected": expected_ties},
        )

    provider = dict(data.get("provider", {}))
    if "timeout_seconds" in provider:
        try:
            provider["timeout_seconds"] = int(provider["timeout_seconds"])
        except (TypeError, ValueError) as exc:
            raise ValidationError(
                "provider.timeout_seconds 必须是整数。",
                code="INVALID_CONFIGURATION_VALUE",
                details={"field": "provider.timeout_seconds"},
            ) from exc
    if "max_tokens" in provider:
        try:
            provider["max_tokens"] = int(provider["max_tokens"])
        except (TypeError, ValueError) as exc:
            raise ValidationError(
                "provider.max_tokens 必须是整数。",
                code="INVALID_CONFIGURATION_VALUE",
                details={"field": "provider.max_tokens"},
            ) from exc
        _positive_int(provider["max_tokens"], "provider.max_tokens")

    return PipelineConfig(
        schema_version=str(data.get("schema_version", "")).strip(),
        generation=GenerationConfig(
            max_attempts=_positive_int(generation.get("max_attempts"), "generation.max_attempts"),
            prompt_versions={key: str(value).strip() for key, value in prompt_versions.items()},
            parameters=dict(generation.get("parameters", {})),
            target_locale=str(generation.get("target_locale", "")).strip(),
            target_market=str(generation.get("target_market", "")).strip(),
            strategy_counts=parsed_strategy_counts,
            coverage_slots=parsed_coverage_slots,
        ),
        scoring=ScoringConfig(
            max_attempts=_positive_int(scoring.get("max_attempts"), "scoring.max_attempts"),
            rubric_version=str(scoring.get("rubric_version", "")).strip(),
            weight_version=str(scoring.get("weight_version", "")).strip(),
            prompt_version=str(scoring.get("prompt_version", "")).strip(),
            permutation_seed=int(scoring.get("permutation_seed", 0)),
            weights={key: int(value) for key, value in weights.items()},
            dimension_guidance={key: str(value) for key, value in guidance.items()},
            tie_break_order=tuple(scoring["tie_break_order"]),
        ),
        provider=provider,
    )


def _resolve_environment_values(value: Any) -> Any:
    """Resolve ``${VARIABLE}`` configuration values from the environment."""

    if isinstance(value, dict):
        return {key: _resolve_environment_values(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_resolve_environment_values(item) for item in value]
    if not isinstance(value, str):
        return value

    match = _ENV_VALUE.fullmatch(value)
    if not match:
        return value
    variable, default = match.groups()
    resolved = os.getenv(variable)
    if resolved is None or not resolved.strip():
        if default is not None:
            return default
        raise ValidationError(
            f"配置所需的环境变量 {variable} 未设置。",
            code="CONFIG_ENVIRONMENT_VARIABLE_MISSING",
            details={"environment_variable": variable},
        )
    return resolved


def load_config(path: str | Path) -> PipelineConfig:
    load_project_dotenv()
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValidationError(
            "无法读取配置 JSON。",
            code="CONFIG_READ_ERROR",
            details={"path": str(path), "error": str(exc)},
        ) from exc
    if not isinstance(data, dict):
        raise ValidationError("配置根节点必须是对象。", code="INVALID_CONFIG_ROOT")
    return parse_config(_resolve_environment_values(data))
