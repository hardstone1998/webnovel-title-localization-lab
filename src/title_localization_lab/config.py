"""Configuration loading and strict validation."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .contracts import DIMENSIONS, STRATEGIES
from .errors import ValidationError


@dataclass(frozen=True)
class GenerationConfig:
    max_attempts: int
    prompt_versions: dict[str, str]
    parameters: dict[str, Any]
    target_locale: str
    target_market: str


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

    return PipelineConfig(
        schema_version=str(data.get("schema_version", "")).strip(),
        generation=GenerationConfig(
            max_attempts=_positive_int(generation.get("max_attempts"), "generation.max_attempts"),
            prompt_versions={key: str(value).strip() for key, value in prompt_versions.items()},
            parameters=dict(generation.get("parameters", {})),
            target_locale=str(generation.get("target_locale", "")).strip(),
            target_market=str(generation.get("target_market", "")).strip(),
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
        provider=dict(data.get("provider", {})),
    )


def load_config(path: str | Path) -> PipelineConfig:
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
    return parse_config(data)
