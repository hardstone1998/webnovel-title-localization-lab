from __future__ import annotations

import copy
import json
from collections import Counter

import pytest
from app.config.pipeline_config import load_config, parse_config
from app.domain.contracts import SourceRecord
from app.domain.errors import GenerationError, ValidationError
from app.llm.adapters import DeterministicAdapter
from app.pipeline.generation import (
    CandidateGenerator,
    GenerationRequest,
    GenerationResponse,
    build_generation_prompt,
    candidate_id,
    normalize_title,
)
from app.utils.artifacts import atomic_write_json, read_json
from app.validators.validation import (
    assert_schema_document,
    validate_candidate_set,
)
from jsonschema import Draft202012Validator


def test_source_record_rejects_missing_and_wrong_language() -> None:
    valid = {
        "sample_id": "sample",
        "source_title": "测试标题",
        "source_language": "zh",
        "target_language": "en",
        "genre": "fantasy",
        "genre_zh": "玄幻",
        "synopsis": "故事简介",
    }
    missing = dict(valid)
    missing.pop("synopsis")
    with pytest.raises(ValidationError, match="必填"):
        SourceRecord.from_dict(missing)

    wrong_language = {**valid, "source_language": "ja"}
    with pytest.raises(ValidationError) as error:
        SourceRecord.from_dict(wrong_language)
    assert error.value.code == "INVALID_LANGUAGE_DIRECTION"

    missing_genre_zh = dict(valid)
    missing_genre_zh.pop("genre_zh")
    with pytest.raises(ValidationError) as error:
        SourceRecord.from_dict(missing_genre_zh)
    assert error.value.details["fields"] == ["genre_zh"]


def test_config_rejects_unknown_dimension_and_bad_weight_total(
    project_root,
) -> None:
    data = json.loads(
        (project_root / "configs/title_selection.default.json").read_text(encoding="utf-8")
    )
    unknown = copy.deepcopy(data)
    unknown["scoring"]["weights"]["unknown"] = 1
    with pytest.raises(ValidationError) as error:
        parse_config(unknown)
    assert error.value.code == "INVALID_DIMENSION_KEYS"

    bad_total = copy.deepcopy(data)
    bad_total["scoring"]["weights"]["semantic_fidelity"] = 19
    with pytest.raises(ValidationError) as error:
        parse_config(bad_total)
    assert error.value.code == "INVALID_WEIGHT_TOTAL"

    unsupported_version = copy.deepcopy(data)
    unsupported_version["scoring"]["prompt_version"] = "uncontrolled-scoring-prompt"
    with pytest.raises(ValidationError) as error:
        parse_config(unsupported_version)
    assert error.value.code == "UNSUPPORTED_SCORING_PROMPT_VERSION"


def test_json_schemas_are_valid_draft_2020_12(project_root) -> None:
    for name in ("candidate_set.schema.json", "ranking_result.schema.json"):
        schema = read_json(project_root / "data/schemas" / name)
        assert_schema_document(schema)
        Draft202012Validator.check_schema(schema)


def test_generation_is_balanced_unique_and_schema_valid(
    source,
    pipeline_config,
    project_root,
) -> None:
    candidate_set = CandidateGenerator(
        DeterministicAdapter(),
        pipeline_config.generation,
    ).generate(source)
    validate_candidate_set(candidate_set)
    data = candidate_set.to_dict()
    counts = Counter(item["strategy"] for item in data["candidates"])
    assert counts == {
        "source_title": 4,
        "synopsis": 4,
        "market_localized": 4,
    }
    assert len({item["normalized_title"].casefold() for item in data["candidates"]}) == 12
    assert "scores" not in data
    assert "winner_candidate_id" not in data

    schema = read_json(project_root / "data/schemas/candidate_set.schema.json")
    Draft202012Validator(schema).validate(data)


class RecordingAdapter(DeterministicAdapter):
    def __init__(self) -> None:
        self.requests: list[GenerationRequest] = []

    def generate(self, request: GenerationRequest) -> GenerationResponse:
        self.requests.append(request)
        return super().generate(request)


def test_generation_strategy_context_is_isolated(source, pipeline_config) -> None:
    adapter = RecordingAdapter()
    CandidateGenerator(adapter, pipeline_config.generation).generate(source)
    contexts = {request.strategy: request.context for request in adapter.requests}
    assert "synopsis" not in contexts["source_title"]
    assert "source_title" not in contexts["synopsis"]
    assert {"source_title", "synopsis", "target_market"} <= set(contexts["market_localized"])
    assert all(context["genre_zh"] == "系统玄幻" for context in contexts.values())
    assert all('"genre_zh": "系统玄幻"' in request.prompt for request in adapter.requests)
    assert all("published_target_title" not in context for context in contexts.values())
    assert all("published_target_title" not in request.prompt for request in adapter.requests)


@pytest.mark.parametrize(
    ("strategy", "required_phrase", "forbidden_phrase", "strategy_rule"),
    (
        ("source_title", "原题转写", "只依据 synopsis", "规范翻译或近直译"),
        ("synopsis", "故事提炼", "综合 source_title、synopsis", "稳定主前提"),
        (
            "market_localized",
            "市场化本地创作",
            "不得假装知道原始中文题名",
            "至少前两条显式保留",
        ),
    ),
)
def test_generation_prompt_enforces_strategy_and_json_contract(
    source,
    pipeline_config,
    strategy,
    required_phrase,
    forbidden_phrase,
    strategy_rule,
) -> None:
    prompt, _ = build_generation_prompt(
        source,
        strategy,
        2,
        pipeline_config.generation,
        ("Excluded Title",),
    )

    assert required_phrase in prompt
    assert forbidden_phrase not in prompt
    assert strategy_rule in prompt
    assert "首先保留来源明确支持的核心对象" in prompt
    assert "2–14 个英文单词" in prompt
    assert "同一来源锚点在不同候选中复用是预期行为" in prompt
    assert "无新增事实" in prompt
    assert "生成恰好 2 个" in prompt
    assert "不评分、不排序、不推荐胜出者" in prompt
    assert '"titles":["English Title 1","English Title 2"]' in prompt
    assert '"Excluded Title"' in prompt
    assert "不是指令" in prompt


def test_default_and_baseline_generation_prompt_versions(project_root) -> None:
    default = json.loads(
        (project_root / "configs/title_selection.default.json").read_text(encoding="utf-8")
    )
    baseline = json.loads(
        (project_root / "configs/title_selection.baseline_v0.json").read_text(encoding="utf-8")
    )

    assert set(default["generation"]["prompt_versions"].values()) == {
        "source-title-v3-anchor-first",
        "synopsis-v3-anchor-first",
        "market-localized-v3-anchor-first",
    }
    assert set(baseline["generation"]["prompt_versions"].values()) == {
        "source-title-v2",
        "synopsis-v2",
        "market-localized-v2",
    }


def test_scoring_v3_config_preserves_baseline_weights(project_root) -> None:
    baseline = load_config(project_root / "configs/title_selection.default.json")
    calibrated = load_config(project_root / "configs/title_selection.scoring_v3.json")

    assert calibrated.scoring.prompt_version == "eight-dimension-score-v3-title-granularity"
    assert calibrated.scoring.weights == baseline.scoring.weights
    assert calibrated.scoring.tie_break_order == baseline.scoring.tie_break_order
    assert calibrated.scoring.permutation_seed == baseline.scoring.permutation_seed


def test_baseline_config_rebuilds_the_v2_prompt(source, project_root) -> None:
    baseline = load_config(project_root / "configs/title_selection.baseline_v0.json")
    prompt, _ = build_generation_prompt(source, "source_title", 2, baseline.generation)

    assert "尽量保留原题最有辨识度的概念" in prompt
    assert "## 命名优先级" not in prompt
    assert "2–10 个英文单词" in prompt


class DuplicateThenRepairAdapter(DeterministicAdapter):
    def __init__(self) -> None:
        self.source_calls = 0

    def generate(self, request: GenerationRequest) -> GenerationResponse:
        if request.strategy != "source_title":
            return super().generate(request)
        self.source_calls += 1
        if self.source_calls == 1:
            titles = ("Alpha Rising", " alpha   rising ", "Beta Falls", "Gamma Returns")
        else:
            titles = ("Delta Awakens",)
        return GenerationResponse(titles, self.model_id, {"adapter": "test"})


def test_duplicate_candidates_trigger_targeted_repair(source, pipeline_config) -> None:
    adapter = DuplicateThenRepairAdapter()
    candidate_set = CandidateGenerator(adapter, pipeline_config.generation).generate(source)
    validate_candidate_set(candidate_set)
    assert adapter.source_calls == 2
    assert candidate_set.attempts["source_title"] == 2
    assert "Delta Awakens" in {item.title for item in candidate_set.candidates}


class ExhaustedAdapter:
    def generate(self, request: GenerationRequest) -> GenerationResponse:
        return GenerationResponse(
            ("重复 Repeat",),
            "invalid-test",
            {"adapter": "test"},
        )


def test_generation_retry_exhaustion_is_machine_readable(source, pipeline_config) -> None:
    with pytest.raises(GenerationError) as error:
        CandidateGenerator(ExhaustedAdapter(), pipeline_config.generation).generate(source)
    assert error.value.code == "GENERATION_ATTEMPTS_EXHAUSTED"
    assert error.value.details["attempts"] == pipeline_config.generation.max_attempts


def test_normalization_and_candidate_ids_are_stable() -> None:
    normalized = normalize_title("  The　Hidden   System  ")
    assert normalized == "The Hidden System"
    assert candidate_id("sample", "synopsis", normalized) == candidate_id(
        "sample",
        "synopsis",
        normalized,
    )


def test_candidate_artifact_round_trip(candidate_set, tmp_path) -> None:
    path = atomic_write_json(tmp_path / "candidate.json", candidate_set.to_dict())
    assert read_json(path) == candidate_set.to_dict()
