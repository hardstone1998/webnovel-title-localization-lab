from __future__ import annotations

import importlib.util
from pathlib import Path


def _batch_module(project_root: Path):
    path = project_root / "scripts" / "run_title_localization_batch.py"
    spec = importlib.util.spec_from_file_location("title_localization_batch", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _record() -> dict[str, str]:
    return {
        "pair_id": "pair-1",
        "zh_title": "测试标题",
        "en_title": "Published Title",
        "genre_en": "Fantasy",
        "genre_zh": "玄幻",
        "zh_synopsis": "测试简介",
    }


def test_batch_rows_keep_candidate_provenance_and_critical_violations(project_root) -> None:
    batch = _batch_module(project_root)
    rows = list(
        batch.rows_from_response(
            _record(),
            {
                "selected": {"candidate_id": "cand_1", "title": "Selected", "score": 88.0},
                "ranked_titles": [
                    {
                        "rank": 1,
                        "candidate_id": "cand_1",
                        "title": "Selected",
                        "strategy": "source_title",
                        "ordinal": 1,
                        "prompt_version": "source-title-v3-anchor-first",
                        "scoring_prompt_version": "eight-dimension-score-v3-title-granularity",
                        "total_score": 88.0,
                        "critical_violation_codes": ["HOOK_INVENTED"],
                        "dimensions": {dimension: 8 for dimension in batch.DIMENSIONS},
                    }
                ],
            },
        )
    )

    assert rows[0]["candidate_strategy"] == "source_title"
    assert rows[0]["candidate_ordinal"] == 1
    assert rows[0]["candidate_prompt_version"] == "source-title-v3-anchor-first"
    assert rows[0]["scoring_prompt_version"] == "eight-dimension-score-v3-title-granularity"
    assert rows[0]["critical_violation_codes"] == '["HOOK_INVENTED"]'
    assert set(rows[0]) == set(batch.CSV_FIELDS)


def test_failed_batch_row_keeps_new_columns_blank(project_root) -> None:
    batch = _batch_module(project_root)
    row = batch.failure_row(_record(), 502, "provider unavailable")

    assert row["candidate_strategy"] == ""
    assert row["candidate_ordinal"] == ""
    assert row["candidate_prompt_version"] == ""
    assert row["scoring_prompt_version"] == ""
    assert row["critical_violation_codes"] == ""
    assert set(row) == set(batch.CSV_FIELDS)
