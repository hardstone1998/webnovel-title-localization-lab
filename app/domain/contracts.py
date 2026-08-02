"""Typed artifact contracts shared by generation, ranking, and reporting."""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field, is_dataclass
from decimal import Decimal
from typing import Any

from .errors import ValidationError

CANDIDATE_SET_SCHEMA_VERSION = "1.0"
RANKING_RESULT_SCHEMA_VERSION = "1.0"
STRATEGIES = ("source_title", "synopsis", "market_localized")
DIMENSIONS = (
    "semantic_fidelity",
    "natural_english",
    "genre_tone_fit",
    "target_market_fit",
    "reader_appeal",
    "memorability_distinctiveness",
    "clarity_concision",
    "integrity_safety",
)
CRITICAL_CODES = {
    "SEMANTIC_MISMATCH",
    "ENTITY_ERROR",
    "GENRE_MISMATCH",
    "HOOK_INVENTED",
}


def _json_ready(value: Any) -> Any:
    if is_dataclass(value):
        return _json_ready(asdict(value))
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, dict):
        return {key: _json_ready(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_ready(item) for item in value]
    return value


def canonical_json(value: Any) -> str:
    return json.dumps(
        _json_ready(value),
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )


def fingerprint(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class SourceRecord:
    sample_id: str
    source_title: str
    source_language: str
    target_language: str
    genre: str
    genre_zh: str
    synopsis: str
    published_target_title: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> SourceRecord:
        required = (
            "sample_id",
            "source_title",
            "source_language",
            "target_language",
            "genre",
            "genre_zh",
            "synopsis",
        )
        missing = [key for key in required if not str(data.get(key, "")).strip()]
        if missing:
            raise ValidationError(
                "源记录缺少必填字段。",
                code="SOURCE_REQUIRED_FIELD_MISSING",
                details={"fields": missing},
            )
        source_language = str(data["source_language"]).lower()
        target_language = str(data["target_language"]).lower()
        if not source_language.startswith("zh") or not target_language.startswith("en"):
            raise ValidationError(
                "仅支持中文到英文的本地化。",
                code="INVALID_LANGUAGE_DIRECTION",
                details={
                    "source_language": data["source_language"],
                    "target_language": data["target_language"],
                },
            )
        metadata = data.get("metadata", {})
        if not isinstance(metadata, dict):
            raise ValidationError(
                "metadata 必须是对象。",
                code="INVALID_SOURCE_METADATA",
            )
        return cls(
            sample_id=str(data["sample_id"]).strip(),
            source_title=str(data["source_title"]).strip(),
            source_language=str(data["source_language"]).strip(),
            target_language=str(data["target_language"]).strip(),
            genre=str(data["genre"]).strip(),
            genre_zh=str(data["genre_zh"]).strip(),
            synopsis=str(data["synopsis"]).strip(),
            published_target_title=str(data.get("published_target_title", "")).strip(),
            metadata=metadata,
        )

    def to_dict(self) -> dict[str, Any]:
        return _json_ready(self)


@dataclass(frozen=True)
class CandidateProvenance:
    model_id: str
    prompt_version: str
    parameters: dict[str, Any]
    attempt: int


@dataclass(frozen=True)
class Candidate:
    candidate_id: str
    title: str
    normalized_title: str
    strategy: str
    ordinal: int
    provenance: CandidateProvenance


@dataclass(frozen=True)
class CandidateSet:
    schema_version: str
    candidate_set_id: str
    sample_id: str
    source_fingerprint: str
    created_at: str
    generation_config: dict[str, Any]
    attempts: dict[str, int]
    candidates: tuple[Candidate, ...]

    def to_dict(self) -> dict[str, Any]:
        return _json_ready(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> CandidateSet:
        candidates = tuple(
            Candidate(
                candidate_id=str(item["candidate_id"]),
                title=str(item["title"]),
                normalized_title=str(item["normalized_title"]),
                strategy=str(item["strategy"]),
                ordinal=int(item["ordinal"]),
                provenance=CandidateProvenance(
                    model_id=str(item["provenance"]["model_id"]),
                    prompt_version=str(item["provenance"]["prompt_version"]),
                    parameters=dict(item["provenance"]["parameters"]),
                    attempt=int(item["provenance"]["attempt"]),
                ),
            )
            for item in data["candidates"]
        )
        return cls(
            schema_version=str(data["schema_version"]),
            candidate_set_id=str(data["candidate_set_id"]),
            sample_id=str(data["sample_id"]),
            source_fingerprint=str(data["source_fingerprint"]),
            created_at=str(data["created_at"]),
            generation_config=dict(data["generation_config"]),
            attempts={key: int(value) for key, value in data["attempts"].items()},
            candidates=candidates,
        )


@dataclass(frozen=True)
class DimensionScore:
    score: int
    rationale: str
    model_contribution: Decimal
    authoritative_contribution: Decimal


@dataclass(frozen=True)
class Violation:
    code: str
    severity: str
    rationale: str
    evidence_field: str = ""


@dataclass(frozen=True)
class CandidateScore:
    candidate_id: str
    title: str
    dimensions: dict[str, DimensionScore]
    violations: tuple[Violation, ...]
    model_total: Decimal
    authoritative_total: Decimal
    arithmetic_mismatch: bool
    eligible: bool


@dataclass(frozen=True)
class RankingResult:
    schema_version: str
    ranking_id: str
    candidate_set_id: str
    candidate_set_fingerprint: str
    sample_id: str
    created_at: str
    rubric_version: str
    weight_version: str
    weights: dict[str, int]
    scoring_provenance: dict[str, Any]
    input_permutation: tuple[str, ...]
    attempts: int
    scores: tuple[CandidateScore, ...]
    ordered_candidate_ids: tuple[str, ...]
    winner_candidate_id: str | None
    outcome: str
    no_winner_reason: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return _json_ready(self)
