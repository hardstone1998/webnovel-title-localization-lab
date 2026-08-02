"""Pydantic request and response contracts for the HTTP API."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

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
    source: SourceRecordRequest
    config_profile: Literal["default", "deepseek"] = "default"
    adapter: Literal["deterministic", "openai-compatible"] = "deterministic"


class LocalizationResponse(BaseModel):
    candidate_set: dict[str, Any]
    ranking_result: dict[str, Any]
    report: str
