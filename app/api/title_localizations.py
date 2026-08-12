"""Title-localization HTTP route."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Request

from ..domain.errors import NoEligibleWinnerError
from ..domain.http_models import (
    LocalizationRequest,
    LocalizationResponse,
    RankedTitleScore,
    SelectedTitle,
)
from ..utils.logging import RunLogContext

router = APIRouter(tags=["title-localizations"])
logger = logging.getLogger(__name__)


@router.post(
    "/v1/title-localizations",
    response_model=LocalizationResponse,
    response_model_exclude_none=True,
)
def localize_title(request: Request, body: LocalizationRequest) -> LocalizationResponse:
    """Generate, score, and return the selected title without persisting artifacts."""

    run_context = RunLogContext(request_id=request.state.request_id)
    outcome = request.app.state.run_localization(body, run_context)
    winner_id = outcome.ranking.winner_candidate_id
    if winner_id is None:
        raise NoEligibleWinnerError(
            "没有符合资格的候选剧名。",
            details={"reason": outcome.ranking.no_winner_reason},
        )

    scores_by_id = {item.candidate_id: item for item in outcome.ranking.scores}
    candidates_by_id = {
        item.candidate_id: item for item in outcome.candidate_set.candidates
    }
    winner = scores_by_id[winner_id]
    selected = SelectedTitle(
        candidate_id=winner.candidate_id,
        title=winner.title,
        score=float(winner.authoritative_total),
    )
    ranked_titles = [
        RankedTitleScore(
            rank=rank,
            candidate_id=scores_by_id[candidate_id].candidate_id,
            title=scores_by_id[candidate_id].title,
            strategy=candidates_by_id[candidate_id].strategy,
            ordinal=candidates_by_id[candidate_id].ordinal,
            prompt_version=candidates_by_id[candidate_id].provenance.prompt_version,
            scoring_prompt_version=str(
                outcome.ranking.scoring_provenance["prompt_version"]
            ),
            dimensions={
                dimension: detail.score
                for dimension, detail in scores_by_id[candidate_id].dimensions.items()
            },
            total_score=float(scores_by_id[candidate_id].authoritative_total),
            critical_violation_codes=[
                violation.code
                for violation in scores_by_id[candidate_id].violations
                if violation.severity == "critical"
            ],
        )
        for rank, candidate_id in enumerate(outcome.ranking.ordered_candidate_ids, start=1)
    ]
    logger.info(
        "selection_completed request_id=%s candidate_id=%s title=%r score=%.2f",
        run_context.correlation_id,
        selected.candidate_id,
        selected.title,
        selected.score,
    )
    return LocalizationResponse(
        selected=selected,
        ranked_titles=ranked_titles,
        debug=ranked_titles if body.debug else None,
    )
