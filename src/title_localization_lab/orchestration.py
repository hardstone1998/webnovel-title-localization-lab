"""End-to-end two-stage pipeline orchestration."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .adapters import create_adapter
from .artifacts import (
    artifact_fingerprint,
    atomic_write_json,
    atomic_write_text,
    read_json,
)
from .config import PipelineConfig, load_config
from .contracts import CandidateSet, RankingResult, SourceRecord
from .errors import LabError
from .generation import CandidateGenerator
from .reporting import render_markdown_report
from .scoring import TitleRanker
from .validation import validate_candidate_set, validate_ranking_result


@dataclass(frozen=True)
class RunOutcome:
    candidate_path: Path
    ranking_path: Path
    report_path: Path
    candidate_set: CandidateSet
    ranking: RankingResult


def _load_source(path: str | Path) -> SourceRecord:
    return SourceRecord.from_dict(read_json(path))


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

        candidate_set = CandidateGenerator(adapter, resolved_config.generation).generate(source)
        validate_candidate_set(candidate_set)
        candidate_path = atomic_write_json(
            output / "candidate_set.json",
            candidate_set.to_dict(),
        )

        frozen_candidate_set = CandidateSet.from_dict(read_json(candidate_path))
        validate_candidate_set(frozen_candidate_set)
        candidate_fingerprint = artifact_fingerprint(candidate_path)

        ranking = TitleRanker(adapter, resolved_config.scoring).rank(
            source,
            frozen_candidate_set,
            candidate_fingerprint,
        )
        validate_ranking_result(ranking, frozen_candidate_set)
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
