"""Machine-readable domain errors for the title-localization pipeline."""

from __future__ import annotations

from typing import Any


class LabError(Exception):
    """Base error carrying a stable code and JSON-serializable details."""

    default_code = "LAB_ERROR"

    def __init__(
        self,
        message: str,
        *,
        code: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.code = code or self.default_code
        self.details = details or {}

    def to_dict(self) -> dict[str, Any]:
        return {"code": self.code, "message": self.message, "details": self.details}


class ValidationError(LabError):
    default_code = "VALIDATION_ERROR"


class GenerationError(LabError):
    default_code = "GENERATION_ERROR"


class ScoringError(LabError):
    default_code = "SCORING_ERROR"


class ProviderError(LabError):
    default_code = "PROVIDER_ERROR"


class NoEligibleWinnerError(LabError):
    default_code = "NO_ELIGIBLE_WINNER"
