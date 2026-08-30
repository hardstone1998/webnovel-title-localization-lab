from __future__ import annotations

from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]

from app.config.pipeline_config import load_config
from app.domain.contracts import SourceRecord
from app.llm.adapters import DeterministicAdapter
from app.pipeline.generation import CandidateGenerator


@pytest.fixture
def project_root() -> Path:
    return ROOT


@pytest.fixture
def source(project_root: Path) -> SourceRecord:
    import json

    data = json.loads(
        (project_root / "data/examples/sample_title_case.json").read_text(encoding="utf-8-sig")
    )
    return SourceRecord.from_dict(data)


@pytest.fixture
def pipeline_config(project_root: Path):
    return load_config(project_root / "configs/title_selection.default.json")


@pytest.fixture
def coverage_matrix_config(project_root: Path):
    return load_config(project_root / "configs/title_selection.coverage_matrix_v1.json")


@pytest.fixture
def candidate_set(source: SourceRecord, pipeline_config):
    return CandidateGenerator(
        DeterministicAdapter(),
        pipeline_config.generation,
    ).generate(source)
