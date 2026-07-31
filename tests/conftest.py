from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from title_localization_lab.adapters import DeterministicAdapter
from title_localization_lab.config import load_config
from title_localization_lab.contracts import SourceRecord
from title_localization_lab.generation import CandidateGenerator


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
def candidate_set(source: SourceRecord, pipeline_config):
    return CandidateGenerator(
        DeterministicAdapter(),
        pipeline_config.generation,
    ).generate(source)
