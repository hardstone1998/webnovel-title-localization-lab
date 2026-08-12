"""Pydantic request and response contracts for the HTTP API."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from .contracts import SourceRecord


class SourceRecordRequest(BaseModel):
    sample_id: str = Field(min_length=1)
    source_title: str = Field(min_length=1)
    source_language: str = Field(min_length=1)
    target_language: str = Field(min_length=1)
    genre: str = Field(min_length=1)
    genre_zh: str = Field(min_length=1)
    synopsis: str = Field(min_length=1)
    published_target_title: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)

    def to_source_record(self) -> SourceRecord:
        return SourceRecord.from_dict(self.model_dump())


class LocalizationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source: SourceRecordRequest
    debug: bool = False


class SelectedTitle(BaseModel):
    candidate_id: str
    title: str
    score: float


class RankedTitleScore(BaseModel):
    """A candidate title and its authoritative scoring result."""

    rank: int
    candidate_id: str
    title: str
    strategy: str
    ordinal: int
    prompt_version: str
    scoring_prompt_version: str
    dimensions: dict[str, int]
    total_score: float
    critical_violation_codes: list[str]


class LocalizationResponse(BaseModel):
    selected: SelectedTitle
    ranked_titles: list[RankedTitleScore]
    debug: list[RankedTitleScore] | None = None
