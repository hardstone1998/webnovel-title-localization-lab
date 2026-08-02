"""Title-localization HTTP route."""

from __future__ import annotations

from fastapi import APIRouter, Request

from ..domain.http_models import LocalizationRequest, LocalizationResponse

router = APIRouter(tags=["title-localizations"])


@router.post("/v1/title-localizations", response_model=LocalizationResponse)
def localize_title(request: Request, body: LocalizationRequest) -> LocalizationResponse:
    """Generate, score, and return title candidates without persisting artifacts."""

    outcome = request.app.state.run_localization(body)
    return LocalizationResponse(
        candidate_set=outcome.candidate_set.to_dict(),
        ranking_result=outcome.ranking.to_dict(),
        report=outcome.report,
    )
