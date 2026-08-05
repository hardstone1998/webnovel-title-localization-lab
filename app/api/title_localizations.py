"""Title-localization HTTP route."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Request

from ..domain.errors import NoEligibleWinnerError
from ..domain.http_models import LocalizationRequest, LocalizationResponse, SelectedTitle
from ..utils.logging import RunLogContext

router = APIRouter(tags=["title-localizations"])
logger = logging.getLogger(__name__)


@router.post("/v1/title-localizations", response_model=LocalizationResponse)
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
    winner = scores_by_id[winner_id]
    unselected_titles = [
        scores_by_id[candidate_id].title
        for candidate_id in outcome.ranking.ordered_candidate_ids
        if candidate_id != winner_id
    ]
    selected = SelectedTitle(
        candidate_id=winner.candidate_id,
        title=winner.title,
        score=float(winner.authoritative_total),
    )
    logger.info(
        "selection_completed request_id=%s candidate_id=%s title=%r score=%.2f "
        "unselected_count=%s",
        run_context.correlation_id,
        selected.candidate_id,
        selected.title,
        selected.score,
        len(unselected_titles),
    )
    return LocalizationResponse(
        selected=selected,
        unselected_titles=unselected_titles,
    )
