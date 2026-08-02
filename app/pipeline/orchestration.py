"""End-to-end two-stage pipeline orchestration."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ..config.pipeline_config import PipelineConfig, load_config
from ..domain.contracts import CandidateSet, RankingResult, SourceRecord, fingerprint
from ..domain.errors import LabError
from ..llm.adapters import create_adapter
from ..utils.artifacts import (
    artifact_fingerprint,
    atomic_write_json,
    atomic_write_text,
    read_json,
)
from ..validators.validation import validate_candidate_set, validate_ranking_result
from .generation import CandidateGenerator
from .reporting import render_markdown_report
from .scoring import TitleRanker


@dataclass(frozen=True)
class RunOutcome:
    candidate_path: Path
    ranking_path: Path
    report_path: Path
    candidate_set: CandidateSet
    ranking: RankingResult


@dataclass(frozen=True)
class InMemoryOutcome:
    """Completed pipeline result for callers that do not persist artifacts."""

    candidate_set: CandidateSet
    ranking: RankingResult
    report: str


def _load_source(path: str | Path) -> SourceRecord:
    return SourceRecord.from_dict(read_json(path))


def _generate_candidate_set(
    source: SourceRecord,
    config: PipelineConfig,
    model_adapter: Any,
) -> CandidateSet:
    candidate_set = CandidateGenerator(model_adapter, config.generation).generate(source)
    validate_candidate_set(candidate_set)
    return candidate_set


def _rank_candidate_set(
    source: SourceRecord,
    candidate_set: CandidateSet,
    candidate_fingerprint: str,
    config: PipelineConfig,
    model_adapter: Any,
) -> RankingResult:
    ranking = TitleRanker(model_adapter, config.scoring).rank(
        source,
        candidate_set,
        candidate_fingerprint,
    )
    validate_ranking_result(ranking, candidate_set)
    return ranking


def run_pipeline_for_source(
    source: SourceRecord,
    config: PipelineConfig,
    *,
    model_adapter: Any,
) -> InMemoryOutcome:
    """Execute the two-stage pipeline without reading or writing artifacts."""

    candidate_set = _generate_candidate_set(source, config, model_adapter)
    ranking = _rank_candidate_set(
        source,
        candidate_set,
        fingerprint(candidate_set.to_dict()),
        config,
        model_adapter,
    )
    return InMemoryOutcome(
        candidate_set=candidate_set,
        ranking=ranking,
        report=render_markdown_report(candidate_set, ranking),
    )


def run_pipeline(
    input_path: str | Path,
    config_path: str | Path,
    output_dir: str | Path,
    *,
    adapter_name: str = "deterministic",
    config: PipelineConfig | None = None,
    model_adapter: Any | None = None,
) -> RunOutcome:
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    try:
        resolved_config = config or load_config(config_path)
        source = _load_source(input_path)
        adapter = model_adapter or create_adapter(adapter_name, resolved_config)

        candidate_set = _generate_candidate_set(source, resolved_config, adapter)
        candidate_path = atomic_write_json(
            output / "candidate_set.json",
            candidate_set.to_dict(),
        )

        frozen_candidate_set = CandidateSet.from_dict(read_json(candidate_path))
        validate_candidate_set(frozen_candidate_set)
        candidate_fingerprint = artifact_fingerprint(candidate_path)

        ranking = _rank_candidate_set(
            source,
            frozen_candidate_set,
            candidate_fingerprint,
            resolved_config,
            adapter,
        )
        ranking_path = atomic_write_json(
            output / "ranking_result.json",
            ranking.to_dict(),
        )
        report_path = atomic_write_text(
            output / "report.md",
            render_markdown_report(frozen_candidate_set, ranking),
        )
        error_path = output / "run_error.json"
        if error_path.exists():
            error_path.unlink()
        return RunOutcome(
            candidate_path=candidate_path,
            ranking_path=ranking_path,
            report_path=report_path,
            candidate_set=frozen_candidate_set,
            ranking=ranking,
        )
    except LabError as exc:
        atomic_write_json(output / "run_error.json", exc.to_dict())
        raise
