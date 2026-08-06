from __future__ import annotations

from dataclasses import replace
from decimal import Decimal

import pytest
from app.domain.contracts import DIMENSIONS, fingerprint
from app.domain.errors import ProviderError, ScoringError
from app.llm.adapters import DeterministicAdapter
from app.pipeline.scoring import (
    ModelCandidateScore,
    ModelDimensionScore,
    ModelViolation,
    ScoringRequest,
    ScoringResponse,
    TitleRanker,
    build_scoring_prompt,
)
from app.validators.validation import validate_ranking_result


class ScoringTransformAdapter(DeterministicAdapter):
    def __init__(self, transform):
        self.transform = transform

    def score(self, request: ScoringRequest) -> ScoringResponse:
        return self.transform(super().score(request))


class ProviderErrorThenSuccessAdapter(DeterministicAdapter):
    def __init__(self, error_code: str) -> None:
        self.error_code = error_code
        self.calls = 0

    def score(self, request: ScoringRequest) -> ScoringResponse:
        self.calls += 1
        if self.calls == 1:
            raise ProviderError("temporary provider failure", code=self.error_code)
        return super().score(request)


class ProviderErrorAdapter(DeterministicAdapter):
    def __init__(self, error_code: str) -> None:
        self.error_code = error_code
        self.calls = 0

    def score(self, request: ScoringRequest) -> ScoringResponse:
        self.calls += 1
        raise ProviderError("provider failure", code=self.error_code)


def rank_with(adapter, source, candidate_set, pipeline_config):
    candidate_fingerprint = fingerprint(candidate_set.to_dict())
    return TitleRanker(adapter, pipeline_config.scoring).rank(
        source,
        candidate_set,
        candidate_fingerprint,
    )


def test_all_candidates_receive_complete_scores_and_one_winner(
    source,
    candidate_set,
    pipeline_config,
) -> None:
    result = rank_with(DeterministicAdapter(), source, candidate_set, pipeline_config)
    validate_ranking_result(result, candidate_set)
    assert len(result.scores) == 12
    assert result.winner_candidate_id in result.ordered_candidate_ids
    assert result.outcome == "winner_selected"
    assert all(set(item.dimensions) == set(DIMENSIONS) for item in result.scores)
    assert all(Decimal(10) <= item.authoritative_total <= Decimal(100) for item in result.scores)


def test_scoring_prompt_includes_chinese_genre_for_model_decision(
    source,
    candidate_set,
    pipeline_config,
) -> None:
    candidates = tuple((item.candidate_id, item.title) for item in candidate_set.candidates)

    prompt = build_scoring_prompt(source, candidates, pipeline_config.scoring)

    assert '"genre_zh": "系统玄幻"' in prompt


def test_scoring_prompt_preserves_frozen_pool_and_exact_output_contract(
    source,
    candidate_set,
    pipeline_config,
) -> None:
    candidates = tuple((item.candidate_id, item.title) for item in candidate_set.candidates)

    prompt = build_scoring_prompt(source, candidates, pipeline_config.scoring)

    assert "不增加、删除、合并、改写标题" in prompt
    assert "不直接选冠军、不输出排名" in prompt
    assert "score × weight ÷ 10" in prompt
    assert "SEMANTIC_MISMATCH" in prompt
    assert "DUPLICATE_CANDIDATE" in prompt
    assert '"scores"' in prompt
    assert all(dimension in prompt for dimension in DIMENSIONS)


def test_incomplete_pool_is_retried_then_rejected(
    source,
    candidate_set,
    pipeline_config,
) -> None:
    def drop_one(response: ScoringResponse) -> ScoringResponse:
        return replace(response, scores=response.scores[:-1])

    with pytest.raises(ScoringError) as error:
        rank_with(
            ScoringTransformAdapter(drop_one),
            source,
            candidate_set,
            pipeline_config,
        )
    assert error.value.code == "SCORING_ATTEMPTS_EXHAUSTED"
    assert error.value.details["attempts"] == pipeline_config.scoring.max_attempts


def test_empty_provider_response_is_retried_then_ranking_succeeds(
    source,
    candidate_set,
    pipeline_config,
    caplog,
) -> None:
    adapter = ProviderErrorThenSuccessAdapter("PROVIDER_RESPONSE_EMPTY")

    result = rank_with(adapter, source, candidate_set, pipeline_config)

    assert adapter.calls == 2
    assert result.attempts == 2
    assert "model_call_retry" in caplog.text
    assert "error_code=PROVIDER_RESPONSE_EMPTY" in caplog.text


def test_nonrecoverable_provider_error_is_not_retried(
    source,
    candidate_set,
    pipeline_config,
) -> None:
    adapter = ProviderErrorAdapter("PROVIDER_CREDENTIAL_MISSING")

    with pytest.raises(ProviderError) as error:
        rank_with(adapter, source, candidate_set, pipeline_config)

    assert error.value.code == "PROVIDER_CREDENTIAL_MISSING"
    assert adapter.calls == 1


def test_out_of_range_score_is_rejected(
    source,
    candidate_set,
    pipeline_config,
) -> None:
    def out_of_range(response: ScoringResponse) -> ScoringResponse:
        first = response.scores[0]
        dimensions = dict(first.dimensions)
        dimensions["semantic_fidelity"] = replace(
            dimensions["semantic_fidelity"],
            score=11,
        )
        return replace(
            response,
            scores=(replace(first, dimensions=dimensions), *response.scores[1:]),
        )

    with pytest.raises(ScoringError):
        rank_with(
            ScoringTransformAdapter(out_of_range),
            source,
            candidate_set,
            pipeline_config,
        )


def test_model_arithmetic_mismatch_is_recorded_but_not_trusted(
    source,
    candidate_set,
    pipeline_config,
) -> None:
    def wrong_math(response: ScoringResponse) -> ScoringResponse:
        first = response.scores[0]
        dimensions = dict(first.dimensions)
        original = dimensions["semantic_fidelity"]
        dimensions["semantic_fidelity"] = replace(
            original,
            weighted_contribution=original.weighted_contribution + Decimal(1),
        )
        changed = replace(
            first,
            dimensions=dimensions,
            weighted_total=first.weighted_total + Decimal(1),
        )
        return replace(response, scores=(changed, *response.scores[1:]))

    result = rank_with(
        ScoringTransformAdapter(wrong_math),
        source,
        candidate_set,
        pipeline_config,
    )
    changed = next(item for item in result.scores if item.arithmetic_mismatch)
    expected = sum(
        (Decimal(detail.score) * Decimal(pipeline_config.scoring.weights[dimension]) / Decimal(10))
        for dimension, detail in changed.dimensions.items()
    )
    assert changed.authoritative_total == expected
    assert changed.model_total != changed.authoritative_total


def test_highest_scoring_critical_candidate_is_excluded(
    source,
    candidate_set,
    pipeline_config,
) -> None:
    excluded_id: str | None = None

    def add_critical(response: ScoringResponse) -> ScoringResponse:
        nonlocal excluded_id
        highest = max(response.scores, key=lambda item: item.weighted_total)
        excluded_id = highest.candidate_id
        changed = replace(
            highest,
            violations=(
                ModelViolation(
                    code="HOOK_INVENTED",
                    severity="critical",
                    rationale="虚构了源内容不存在的卖点。",
                    evidence_field="synopsis",
                ),
            ),
        )
        scores = tuple(
            changed if item.candidate_id == highest.candidate_id else item
            for item in response.scores
        )
        return replace(response, scores=scores)

    result = rank_with(
        ScoringTransformAdapter(add_critical),
        source,
        candidate_set,
        pipeline_config,
    )
    assert excluded_id is not None
    assert result.winner_candidate_id != excluded_id
    excluded = next(item for item in result.scores if item.candidate_id == excluded_id)
    assert not excluded.eligible


def test_all_critical_candidates_produce_no_winner(
    source,
    candidate_set,
    pipeline_config,
) -> None:
    def all_critical(response: ScoringResponse) -> ScoringResponse:
        return replace(
            response,
            scores=tuple(
                replace(
                    item,
                    violations=(
                        ModelViolation(
                            code="SEMANTIC_MISMATCH",
                            severity="critical",
                            rationale="与源内容不符。",
                        ),
                    ),
                )
                for item in response.scores
            ),
        )

    result = rank_with(
        ScoringTransformAdapter(all_critical),
        source,
        candidate_set,
        pipeline_config,
    )
    assert result.winner_candidate_id is None
    assert result.outcome == "no_eligible_winner"
    assert result.no_winner_reason


class TieAdapter(DeterministicAdapter):
    def score(self, request: ScoringRequest) -> ScoringResponse:
        model_scores = []
        preferred_id = request.candidates[0][0]
        for candidate_id, title in request.candidates:
            dimensions = {}
            for dimension in DIMENSIONS:
                score = 5
                if candidate_id == preferred_id and dimension == "semantic_fidelity":
                    score = 6
                if candidate_id == preferred_id and dimension == "clarity_concision":
                    score = 3
                contribution = Decimal(score) * Decimal(request.weights[dimension]) / Decimal(10)
                dimensions[dimension] = ModelDimensionScore(
                    score=score,
                    rationale="同分规则测试。",
                    weighted_contribution=contribution,
                )
            total = sum(item.weighted_contribution for item in dimensions.values())
            model_scores.append(
                ModelCandidateScore(
                    candidate_id=candidate_id,
                    title=title,
                    dimensions=dimensions,
                    violations=(),
                    weighted_total=total,
                )
            )
        return ScoringResponse(tuple(model_scores), self.model_id, {"adapter": "tie-test"})


def test_ties_are_broken_by_semantic_fidelity(
    source,
    candidate_set,
    pipeline_config,
) -> None:
    result = rank_with(TieAdapter(), source, candidate_set, pipeline_config)
    preferred_id = result.input_permutation[0]
    assert result.winner_candidate_id == preferred_id
