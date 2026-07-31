"""Runtime contract validation independent of external JSON-schema libraries."""

from __future__ import annotations

from collections import Counter
from typing import Any

from .contracts import (
    CANDIDATE_SET_SCHEMA_VERSION,
    DIMENSIONS,
    RANKING_RESULT_SCHEMA_VERSION,
    STRATEGIES,
    CandidateSet,
    RankingResult,
)
from .errors import ValidationError
from .generation import candidate_id, is_english_title, normalize_title


def validate_candidate_set(candidate_set: CandidateSet) -> None:
    if candidate_set.schema_version != CANDIDATE_SET_SCHEMA_VERSION:
        raise ValidationError(
            "候选集 Schema 版本无效。",
            code="INVALID_CANDIDATE_SCHEMA_VERSION",
        )
    if len(candidate_set.candidates) != 12:
        raise ValidationError(
            "候选集必须恰好包含 12 个候选。",
            code="INVALID_CANDIDATE_COUNT",
            details={"count": len(candidate_set.candidates)},
        )
    counts = Counter(item.strategy for item in candidate_set.candidates)
    if counts != Counter({strategy: 4 for strategy in STRATEGIES}):
        raise ValidationError(
            "候选集必须满足三种策略各四个。",
            code="INVALID_STRATEGY_COUNTS",
            details={"counts": dict(counts)},
        )
    ids: set[str] = set()
    normalized: set[str] = set()
    ordinals: dict[str, set[int]] = {strategy: set() for strategy in STRATEGIES}
    for item in candidate_set.candidates:
        expected_title = normalize_title(item.title)
        expected_id = candidate_id(candidate_set.sample_id, item.strategy, expected_title)
        if (
            not is_english_title(expected_title)
            or item.normalized_title != expected_title
            or item.candidate_id != expected_id
        ):
            raise ValidationError(
                "候选文本或稳定 ID 无效。",
                code="INVALID_CANDIDATE_IDENTITY",
                details={"candidate_id": item.candidate_id},
            )
        key = expected_title.casefold()
        if item.candidate_id in ids or key in normalized:
            raise ValidationError(
                "候选 ID 或剧名重复。",
                code="DUPLICATE_CANDIDATE",
                details={"candidate_id": item.candidate_id},
            )
        ids.add(item.candidate_id)
        normalized.add(key)
        ordinals[item.strategy].add(item.ordinal)
    if any(values != {1, 2, 3, 4} for values in ordinals.values()):
        raise ValidationError(
            "每种策略的候选序号必须是 1 到 4。",
            code="INVALID_STRATEGY_ORDINALS",
        )


def validate_ranking_result(
    result: RankingResult,
    candidate_set: CandidateSet,
) -> None:
    if result.schema_version != RANKING_RESULT_SCHEMA_VERSION:
        raise ValidationError(
            "排名结果 Schema 版本无效。",
            code="INVALID_RANKING_SCHEMA_VERSION",
        )
    expected_ids = {item.candidate_id for item in candidate_set.candidates}
    score_ids = {item.candidate_id for item in result.scores}
    ordered_ids = set(result.ordered_candidate_ids)
    if len(result.scores) != 12 or score_ids != expected_ids or ordered_ids != expected_ids:
        raise ValidationError(
            "排名结果必须完整覆盖冻结候选池。",
            code="RANKING_POOL_MISMATCH",
        )
    if set(result.weights) != set(DIMENSIONS) or sum(result.weights.values()) != 100:
        raise ValidationError(
            "排名制品中的权重无效。",
            code="INVALID_RANKING_WEIGHTS",
        )
    if result.winner_candidate_id is None:
        if result.outcome != "no_eligible_winner" or not result.no_winner_reason:
            raise ValidationError(
                "无胜出者结果缺少明确原因。",
                code="INVALID_NO_WINNER_RESULT",
            )
    elif (
        result.outcome != "winner_selected"
        or result.winner_candidate_id not in expected_ids
        or result.no_winner_reason is not None
    ):
        raise ValidationError(
            "胜出者结果无效。",
            code="INVALID_WINNER_RESULT",
        )


def assert_schema_document(schema: dict[str, Any]) -> None:
    required = {"$schema", "title", "type", "required", "properties"}
    if not required.issubset(schema):
        raise ValidationError(
            "JSON Schema 文档缺少基础关键字。",
            code="INVALID_JSON_SCHEMA_DOCUMENT",
            details={"missing": sorted(required - set(schema))},
        )
