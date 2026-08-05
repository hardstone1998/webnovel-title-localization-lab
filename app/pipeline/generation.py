"""Strategy-diverse candidate generation."""

from __future__ import annotations

import json
import logging
import re
import time
import unicodedata
from dataclasses import dataclass
from datetime import datetime, timezone
from hashlib import sha256
from typing import Any, Protocol

from ..config.pipeline_config import GenerationConfig
from ..domain.contracts import (
    CANDIDATE_SET_SCHEMA_VERSION,
    STRATEGIES,
    Candidate,
    CandidateProvenance,
    CandidateSet,
    SourceRecord,
    fingerprint,
)
from ..domain.errors import GenerationError
from ..utils.logging import RunLogContext

_CJK_PATTERN = re.compile(r"[\u3400-\u4dbf\u4e00-\u9fff]")
_ASCII_LETTER_PATTERN = re.compile(r"[A-Za-z]")
logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class GenerationRequest:
    strategy: str
    count: int
    prompt: str
    context: dict[str, Any]
    excluded_titles: tuple[str, ...] = ()


@dataclass(frozen=True)
class GenerationResponse:
    titles: tuple[str, ...]
    model_id: str
    provider_metadata: dict[str, Any]


class GenerationModel(Protocol):
    def generate(self, request: GenerationRequest) -> GenerationResponse:
        """Return structured English title candidates."""


def normalize_title(title: str) -> str:
    return " ".join(unicodedata.normalize("NFKC", title).strip().split())


def is_english_title(title: str) -> bool:
    return (
        bool(title) and bool(_ASCII_LETTER_PATTERN.search(title)) and not _CJK_PATTERN.search(title)
    )


def candidate_id(sample_id: str, strategy: str, normalized_title: str) -> str:
    identity = (
        f"{CANDIDATE_SET_SCHEMA_VERSION}|{sample_id}|{strategy}|{normalized_title.casefold()}"
    )
    return f"cand_{sha256(identity.encode('utf-8')).hexdigest()[:16]}"


def generation_context(
    source: SourceRecord,
    strategy: str,
    config: GenerationConfig,
) -> dict[str, Any]:
    shared = {
        "genre": source.genre,
        "genre_zh": source.genre_zh,
        "target_locale": config.target_locale,
    }
    if strategy == "source_title":
        return {**shared, "source_title": source.source_title}
    if strategy == "synopsis":
        return {**shared, "synopsis": source.synopsis}
    if strategy == "market_localized":
        return {
            **shared,
            "source_title": source.source_title,
            "synopsis": source.synopsis,
            "target_market": config.target_market,
        }
    raise GenerationError(
        "未知生成策略。",
        code="UNKNOWN_GENERATION_STRATEGY",
        details={"strategy": strategy},
    )


def build_generation_prompt(
    source: SourceRecord,
    strategy: str,
    count: int,
    config: GenerationConfig,
    excluded_titles: tuple[str, ...] = (),
) -> tuple[str, dict[str, Any]]:
    context = generation_context(source, strategy, config)
    strategy_instruction = {
        "source_title": "仅改编中文原始剧名的核心概念，不得从故事简介虚构卖点。",
        "synopsis": "根据故事简介中的前提、冲突、主角或卖点创作英文剧名。",
        "market_localized": "结合全部上下文，创作符合目标英语市场习惯的本土化剧名。",
    }[strategy]
    prompt = (
        f"生成 {count} 个互不重复、非空且自然的英文剧名。{strategy_instruction}\n"
        f"上下文：{json.dumps(context, ensure_ascii=False, sort_keys=True)}\n"
        f"不得使用：{json.dumps(excluded_titles, ensure_ascii=False)}\n"
        '只返回 JSON：{"titles":["..."]}。不得评分或选择胜出者。'
    )
    return prompt, context


class CandidateGenerator:
    def __init__(
        self,
        model: GenerationModel,
        config: GenerationConfig,
        *,
        run_context: RunLogContext | None = None,
    ) -> None:
        self.model = model
        self.config = config
        self.run_context = run_context or RunLogContext()

    def generate(self, source: SourceRecord) -> CandidateSet:
        candidates: list[Candidate] = []
        seen: set[str] = set()
        attempts: dict[str, int] = {}

        for strategy in STRATEGIES:
            strategy_candidates: list[Candidate] = []
            attempt = 0
            while len(strategy_candidates) < 4 and attempt < self.config.max_attempts:
                attempt += 1
                needed = 4 - len(strategy_candidates)
                excluded = tuple(item.normalized_title for item in candidates)
                prompt, context = build_generation_prompt(
                    source,
                    strategy,
                    needed,
                    self.config,
                    excluded,
                )
                request = GenerationRequest(
                    strategy=strategy,
                    count=needed,
                    prompt=prompt,
                    context=context,
                    excluded_titles=excluded,
                )
                model_id = str(getattr(self.model, "model_id", "unknown"))
                logger.info(
                    "model_call_started request_id=%s stage=generation strategy=%s "
                    "attempt=%s model_id=%s",
                    self.run_context.correlation_id,
                    strategy,
                    attempt,
                    model_id,
                )
                started_at = time.monotonic()
                try:
                    response = self.model.generate(request)
                except Exception as exc:
                    logger.error(
                        "model_call_failed request_id=%s stage=generation strategy=%s "
                        "attempt=%s model_id=%s error_code=%s",
                        self.run_context.correlation_id,
                        strategy,
                        attempt,
                        model_id,
                        getattr(exc, "code", "MODEL_CALL_FAILED"),
                    )
                    raise
                duration_ms = round((time.monotonic() - started_at) * 1000)
                logger.info(
                    "model_call_completed request_id=%s stage=generation strategy=%s "
                    "attempt=%s model_id=%s duration_ms=%s titles=%r",
                    self.run_context.correlation_id,
                    strategy,
                    attempt,
                    response.model_id,
                    duration_ms,
                    list(response.titles),
                )
                if len(response.titles) > needed:
                    raise GenerationError(
                        "生成模型返回的候选数量超过请求数量。",
                        code="GENERATION_RESPONSE_OVERFILLED",
                        details={
                            "strategy": strategy,
                            "requested": needed,
                            "received": len(response.titles),
                        },
                    )
                for raw_title in response.titles:
                    title = normalize_title(str(raw_title))
                    key = title.casefold()
                    if not is_english_title(title) or key in seen:
                        continue
                    ordinal = len(strategy_candidates) + 1
                    candidate = Candidate(
                        candidate_id=candidate_id(source.sample_id, strategy, title),
                        title=title,
                        normalized_title=title,
                        strategy=strategy,
                        ordinal=ordinal,
                        provenance=CandidateProvenance(
                            model_id=response.model_id,
                            prompt_version=self.config.prompt_versions[strategy],
                            parameters={
                                **self.config.parameters,
                                "provider_metadata": response.provider_metadata,
                            },
                            attempt=attempt,
                        ),
                    )
                    strategy_candidates.append(candidate)
                    candidates.append(candidate)
                    seen.add(key)
                    if len(strategy_candidates) == 4:
                        break
                if len(strategy_candidates) < 4 and attempt < self.config.max_attempts:
                    logger.warning(
                        "model_response_rejected request_id=%s stage=generation strategy=%s "
                        "attempt=%s error_code=GENERATION_RESPONSE_INSUFFICIENT",
                        self.run_context.correlation_id,
                        strategy,
                        attempt,
                    )
            attempts[strategy] = attempt
            if len(strategy_candidates) != 4:
                raise GenerationError(
                    "生成策略未能提供四个有效且唯一的候选。",
                    code="GENERATION_ATTEMPTS_EXHAUSTED",
                    details={
                        "strategy": strategy,
                        "valid_count": len(strategy_candidates),
                        "attempts": attempt,
                    },
                )

        candidate_payload = [
            {
                "candidate_id": item.candidate_id,
                "title": item.title,
                "strategy": item.strategy,
                "ordinal": item.ordinal,
            }
            for item in candidates
        ]
        candidate_set_id = f"cset_{fingerprint(candidate_payload)[:16]}"
        return CandidateSet(
            schema_version=CANDIDATE_SET_SCHEMA_VERSION,
            candidate_set_id=candidate_set_id,
            sample_id=source.sample_id,
            source_fingerprint=fingerprint(source.to_dict()),
            created_at=datetime.now(timezone.utc).isoformat(),
            generation_config={
                "max_attempts": self.config.max_attempts,
                "prompt_versions": self.config.prompt_versions,
                "parameters": self.config.parameters,
                "target_locale": self.config.target_locale,
                "target_market": self.config.target_market,
            },
            attempts=attempts,
            candidates=tuple(candidates),
        )
