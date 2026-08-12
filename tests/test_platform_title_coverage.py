from __future__ import annotations

import importlib.util
from pathlib import Path


def _coverage_module(project_root: Path):
    path = project_root / "scripts" / "evaluate_platform_title_coverage.py"
    spec = importlib.util.spec_from_file_location("platform_title_coverage", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _row(
    pair_id: str,
    title: str,
    *,
    rank: int,
    strategy: str,
    selected_title: str | None = None,
    critical: str = "[]",
) -> dict[str, str]:
    return {
        "pair_id": pair_id,
        "published_target_title": "Published Title",
        "status": "success",
        "selected_title": selected_title or ("Published Title" if rank == 1 else "Different Title"),
        "rank": str(rank),
        "candidate_id": f"cand_{pair_id}_{rank}",
        "candidate_title": title,
        "candidate_strategy": strategy,
        "candidate_prompt_version": f"{strategy}-v3-anchor-first",
        "scoring_prompt_version": "eight-dimension-score-v3-title-granularity",
        "critical_violation_codes": critical,
    }


def test_evaluate_reports_platform_coverage_and_strategy_breakdown(project_root) -> None:
    coverage = _coverage_module(project_root)
    rows = [
        _row("one", "Published Title", rank=1, strategy="source_title"),
        _row("one", "Another Title", rank=2, strategy="synopsis"),
        _row(
            "two",
            "Different Title",
            rank=1,
            strategy="source_title",
            selected_title="Different Title",
        ),
        _row(
            "two",
            "Published Title",
            rank=3,
            strategy="market_localized",
            critical='["HOOK_INVENTED"]',
        ),
    ]

    report = coverage.evaluate(rows, expected_candidates=2)

    assert report["records"]["candidate_completeness_rate"] == 1.0
    assert report["platform_title_coverage"] == {
        "top_1_agreement": 0.5,
        "hit_at_3": 1.0,
        "hit_any": 1.0,
        "matched_records": 2,
        "mean_rank_when_hit": 2.0,
    }
    assert report["critical_violations"]["candidate_rate"] == 0.25
    assert report["strategy_coverage"]["source_title"]["record_hit_any"] == 0.5
    assert report["strategy_coverage"]["market_localized"]["record_hit_any"] == 0.5
    assert report["scoring_prompt_versions"] == {
        "eight-dimension-score-v3-title-granularity": 4
    }


def test_evaluate_derives_selection_from_rank_when_rescore_output_has_no_selected_title(
    project_root,
) -> None:
    coverage = _coverage_module(project_root)
    row = _row("one", "Published Title", rank=1, strategy="source_title")
    row.pop("selected_title")

    report = coverage.evaluate([row], expected_candidates=1)

    assert report["platform_title_coverage"]["top_1_agreement"] == 1.0
