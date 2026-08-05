"""Eight-dimension model scoring and deterministic weighted ranking."""

from __future__ import annotations

import json
import logging
import random
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from typing import Any, Protocol

from ..config.pipeline_config import ScoringConfig
from ..domain.contracts import (
    CRITICAL_CODES,
    DIMENSIONS,
    RANKING_RESULT_SCHEMA_VERSION,
    CandidateScore,
    CandidateSet,
    DimensionScore,
    RankingResult,
    SourceRecord,
    Violation,
    fingerprint,
)
from ..domain.errors import ScoringError, ValidationError
from ..utils.logging import RunLogContext

_TWO_PLACES = Decimal("0.01")
_ALLOWED_SEVERITIES = {"critical", "major", "minor", "note"}
logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ModelDimensionScore:
    score: int
    rationale: str
    weighted_contribution: Decimal


@dataclass(frozen=True)
class ModelViolation:
    code: str
    severity: str
    rationale: str
    evidence_field: str = ""


@dataclass(frozen=True)
class ModelCandidateScore:
    candidate_id: str
    title: str
    dimensions: dict[str, ModelDimensionScore]
    violations: tuple[ModelViolation, ...]
    weighted_total: Decimal


@dataclass(frozen=True)
class ScoringRequest:
    prompt: str
    candidates: tuple[tuple[str, str], ...]
    weights: dict[str, int]
    permutation_seed: int


@dataclass(frozen=True)
class ScoringResponse:
    scores: tuple[ModelCandidateScore, ...]
    model_id: str
    provider_metadata: dict[str, Any]


class ScoringModel(Protocol):
    def score(self, request: ScoringRequest) -> ScoringResponse:
        """Return structured dimension scores for the frozen candidate pool."""


def _as_decimal(value: Any, field_name: str) -> Decimal:
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise ValidationError(
            f"{field_name} 必须是数值。",
            code="INVALID_SCORE_NUMBER",
            details={"field": field_name, "value": str(value)},
        ) from exc


def permute_candidates(
    candidate_set: CandidateSet,
    seed: int,
) -> tuple[tuple[str, str], ...]:
    values = [(item.candidate_id, item.title) for item in candidate_set.candidates]
    random.Random(seed).shuffle(values)
    return tuple(values)


def build_scoring_prompt(
    source: SourceRecord,
    candidates: tuple[tuple[str, str], ...],
    config: ScoringConfig,
) -> str:
    rubric = {
        dimension: {
            "weight": config.weights[dimension],
            "guidance": config.dimension_guidance[dimension],
            "scale": "1-10 integer",
        }
        for dimension in DIMENSIONS
    }
    source_context = {
        "source_title": source.source_title,
        "synopsis": source.synopsis,
        "genre": source.genre,
        "genre_zh": source.genre_zh,
        "source_language": source.source_language,
        "target_language": source.target_language,
    }
    candidate_payload = [
        {"candidate_id": candidate_id, "title": title} for candidate_id, title in candidates
    ]
    return (
        "你是英文剧名评审。独立评估全部候选，不得增加、删除、改写剧名，也不得推断生成策略。\n"
        f"源内容：{json.dumps(source_context, ensure_ascii=False, sort_keys=True)}\n"
        f"评分标准：{json.dumps(rubric, ensure_ascii=False, sort_keys=True)}\n"
        f"候选：{json.dumps(candidate_payload, ensure_ascii=False)}\n"
        "每个候选必须给出八项整数得分、简短理由、按权重计算的贡献和总分。"
        "同时标记错误代码及 critical/major/minor/note 严重度。"
        "其中 SEMANTIC_MISMATCH、ENTITY_ERROR、GENRE_MISMATCH、HOOK_INVENTED "
        "可构成严重违规。只返回结构化 JSON。"
    )


def _validate_model_score(
    model_score: ModelCandidateScore,
    expected_title: str,
) -> None:
    if model_score.title != expected_title:
        raise ValidationError(
            "评分响应修改了候选剧名。",
            code="SCORING_TITLE_MUTATION",
            details={"candidate_id": model_score.candidate_id},
        )
    if set(model_score.dimensions) != set(DIMENSIONS):
        raise ValidationError(
            "评分响应未准确覆盖八个维度。",
            code="SCORING_DIMENSION_MISMATCH",
            details={
                "candidate_id": model_score.candidate_id,
                "dimensions": sorted(model_score.dimensions),
            },
        )
    for dimension, item in model_score.dimensions.items():
        if isinstance(item.score, bool) or not isinstance(item.score, int):
            raise ValidationError(
                "维度分数必须是整数。",
                code="NON_INTEGER_DIMENSION_SCORE",
                details={"candidate_id": model_score.candidate_id, "dimension": dimension},
            )
        if not 1 <= item.score <= 10:
            raise ValidationError(
                "维度分数必须在 1 到 10 之间。",
                code="DIMENSION_SCORE_OUT_OF_RANGE",
                details={
                    "candidate_id": model_score.candidate_id,
                    "dimension": dimension,
                    "score": item.score,
                },
            )
        if not item.rationale.strip():
            raise ValidationError(
                "每个维度都必须提供评分理由。",
                code="MISSING_SCORE_RATIONALE",
                details={"candidate_id": model_score.candidate_id, "dimension": dimension},
            )
        _as_decimal(item.weighted_contribution, "weighted_contribution")
    _as_decimal(model_score.weighted_total, "weighted_total")
    for violation in model_score.violations:
        if (
            not violation.code.strip()
            or violation.severity.lower() not in _ALLOWED_SEVERITIES
            or not violation.rationale.strip()
        ):
            raise ValidationError(
                "违规记录无效。",
                code="INVALID_VIOLATION_RECORD",
                details={"candidate_id": model_score.candidate_id},
            )


def _validate_response(
    response: ScoringResponse,
    candidates: tuple[tuple[str, str], ...],
) -> None:
    expected = dict(candidates)
    received_ids = [item.candidate_id for item in response.scores]
    if (
        len(response.scores) != 12
        or len(set(received_ids)) != 12
        or set(received_ids) != set(expected)
    ):
        raise ValidationError(
            "评分响应必须恰好覆盖冻结候选池中的全部 12 个候选。",
            code="SCORING_POOL_MISMATCH",
            details={
                "expected_ids": sorted(expected),
                "received_ids": sorted(received_ids),
            },
        )
    for model_score in response.scores:
        _validate_model_score(model_score, expected[model_score.candidate_id])


def _authoritative_candidate_score(
    model_score: ModelCandidateScore,
    weights: dict[str, int],
) -> CandidateScore:
    dimensions: dict[str, DimensionScore] = {}
    mismatch = False
    total = Decimal(0)
    for dimension in DIMENSIONS:
        model_dimension = model_score.dimensions[dimension]
        authoritative = (
            Decimal(model_dimension.score) * Decimal(weights[dimension]) / Decimal(10)
        ).quantize(_TWO_PLACES, rounding=ROUND_HALF_UP)
        model_contribution = _as_decimal(
            model_dimension.weighted_contribution,
            f"{dimension}.weighted_contribution",
        ).quantize(_TWO_PLACES, rounding=ROUND_HALF_UP)
        if model_contribution != authoritative:
            mismatch = True
        total += authoritative
        dimensions[dimension] = DimensionScore(
            score=model_dimension.score,
            rationale=model_dimension.rationale.strip(),
            model_contribution=model_contribution,
            authoritative_contribution=authoritative,
        )
    total = total.quantize(_TWO_PLACES, rounding=ROUND_HALF_UP)
    model_total = _as_decimal(model_score.weighted_total, "weighted_total").quantize(
        _TWO_PLACES,
        rounding=ROUND_HALF_UP,
    )
    if model_total != total:
        mismatch = True
    violations = tuple(
        Violation(
            code=item.code.strip(),
            severity=item.severity.lower(),
            rationale=item.rationale.strip(),
            evidence_field=item.evidence_field.strip(),
        )
        for item in model_score.violations
    )
    eligible = not any(
        item.severity == "critical" and item.code in CRITICAL_CODES for item in violations
    )
    return CandidateScore(
        candidate_id=model_score.candidate_id,
        title=model_score.title,
        dimensions=dimensions,
        violations=violations,
        model_total=model_total,
        authoritative_total=total,
        arithmetic_mismatch=mismatch,
        eligible=eligible,
    )


def _ranking_key(item: CandidateScore) -> tuple[Any, ...]:
    return (
        0 if item.eligible else 1,
        -item.authoritative_total,
        -item.dimensions["semantic_fidelity"].score,
        -item.dimensions["integrity_safety"].score,
        -item.dimensions["natural_english"].score,
        item.candidate_id,
    )


class TitleRanker:
    def __init__(
        self,
        model: ScoringModel,
        config: ScoringConfig,
        *,
        run_context: RunLogContext | None = None,
    ) -> None:
        self.model = model
        self.config = config
        self.run_context = run_context or RunLogContext()

    def rank(
        self,
        source: SourceRecord,
        candidate_set: CandidateSet,
        candidate_set_fingerprint: str,
    ) -> RankingResult:
        permutation = permute_candidates(candidate_set, self.config.permutation_seed)
        prompt = build_scoring_prompt(source, permutation, self.config)
        request = ScoringRequest(
            prompt=prompt,
            candidates=permutation,
            weights=self.config.weights,
            permutation_seed=self.config.permutation_seed,
        )
        last_error: ValidationError | None = None
        response: ScoringResponse | None = None
        attempt = 0
        for attempt in range(1, self.config.max_attempts + 1):
            model_id = str(getattr(self.model, "model_id", "unknown"))
            logger.info(
                "model_call_started request_id=%s stage=scoring attempt=%s model_id=%s",
                self.run_context.correlation_id,
                attempt,
                model_id,
            )
            started_at = time.monotonic()
            try:
                response = self.model.score(request)
            except Exception as exc:
                logger.error(
                    "model_call_failed request_id=%s stage=scoring attempt=%s model_id=%s "
                    "error_code=%s",
                    self.run_context.correlation_id,
                    attempt,
                    model_id,
                    getattr(exc, "code", "MODEL_CALL_FAILED"),
                )
                raise
            duration_ms = round((time.monotonic() - started_at) * 1000)
            try:
                _validate_response(response, permutation)
                break
            except ValidationError as exc:
                logger.warning(
                    "model_response_rejected request_id=%s stage=scoring attempt=%s "
                    "error_code=%s",
                    self.run_context.correlation_id,
                    attempt,
                    exc.code,
                )
                last_error = exc
                response = None
        if response is None:
            raise ScoringError(
                "评分响应在有限重试后仍未通过校验。",
                code="SCORING_ATTEMPTS_EXHAUSTED",
                details={
                    "attempts": attempt,
                    "last_error": last_error.to_dict() if last_error else None,
                },
            )

        scores = tuple(
            _authoritative_candidate_score(model_score, self.config.weights)
            for model_score in response.scores
        )
        logger.info(
            "model_call_completed request_id=%s stage=scoring attempt=%s model_id=%s "
            "duration_ms=%s scores=%r",
            self.run_context.correlation_id,
            attempt,
            response.model_id,
            duration_ms,
            [
                (item.candidate_id, str(item.authoritative_total), item.eligible)
                for item in scores
            ],
        )
        ordered = tuple(sorted(scores, key=_ranking_key))
        winner = next((item for item in ordered if item.eligible), None)
        outcome = "winner_selected" if winner else "no_eligible_winner"
        no_winner_reason = None if winner else "全部候选均触发严重违规。"
        ranking_payload = {
            "candidate_set_fingerprint": candidate_set_fingerprint,
            "rubric_version": self.config.rubric_version,
            "weight_version": self.config.weight_version,
            "weights": self.config.weights,
            "scores": [
                {
                    "candidate_id": item.candidate_id,
                    "authoritative_total": item.authoritative_total,
                    "eligible": item.eligible,
                }
                for item in ordered
            ],
        }
        return RankingResult(
            schema_version=RANKING_RESULT_SCHEMA_VERSION,
            ranking_id=f"rank_{fingerprint(ranking_payload)[:16]}",
            candidate_set_id=candidate_set.candidate_set_id,
            candidate_set_fingerprint=candidate_set_fingerprint,
            sample_id=candidate_set.sample_id,
            created_at=datetime.now(timezone.utc).isoformat(),
            rubric_version=self.config.rubric_version,
            weight_version=self.config.weight_version,
            weights=dict(self.config.weights),
            scoring_provenance={
                "model_id": response.model_id,
                "prompt_version": self.config.prompt_version,
                "permutation_seed": self.config.permutation_seed,
                "provider_metadata": response.provider_metadata,
            },
            input_permutation=tuple(candidate_id for candidate_id, _ in permutation),
            attempts=attempt,
            scores=scores,
            ordered_candidate_ids=tuple(item.candidate_id for item in ordered),
            winner_candidate_id=winner.candidate_id if winner else None,
            outcome=outcome,
            no_winner_reason=no_winner_reason,
        )
