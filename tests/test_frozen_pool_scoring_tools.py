from __future__ import annotations

import csv
import importlib.util
from pathlib import Path


def _module(project_root: Path, name: str):
    path = project_root / "scripts" / name
    spec = importlib.util.spec_from_file_location(path.stem, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _row(pair_id: str, candidate_id: str, title: str, rank: int, score: int) -> dict[str, str]:
    return {
        "pair_id": pair_id,
        "published_target_title": "Published Title",
        "scoring_prompt_version": "eight-dimension-score-v2",
        "rank": str(rank),
        "candidate_id": candidate_id,
        "candidate_title": title,
        "candidate_total_score": str(score),
        **{dimension: "8" for dimension in (
            "semantic_fidelity", "natural_english", "genre_tone_fit", "target_market_fit",
            "reader_appeal", "memorability_distinctiveness", "clarity_concision", "integrity_safety",
        )},
    }


def test_compare_requires_identical_frozen_candidate_ids(project_root, tmp_path) -> None:
    comparison = _module(project_root, "compare_frozen_pool_scores.py")
    baseline = tmp_path / "baseline.csv"
    calibrated = tmp_path / "calibrated.csv"
    fields = tuple(comparison.REQUIRED_COLUMNS)
    for path, candidate_id in ((baseline, "cand_a"), (calibrated, "cand_b")):
        with path.open("w", encoding="utf-8-sig", newline="") as output:
            writer = csv.DictWriter(output, fieldnames=fields)
            writer.writeheader()
            writer.writerow(_row("pair-1", candidate_id, "Published Title", 1, 80))

    try:
        comparison.compare(baseline, calibrated)
    except ValueError as error:
        assert "candidate IDs differ" in str(error)
    else:
        raise AssertionError("comparison must reject a changed candidate pool")


def test_compare_reports_weak_positive_metrics_and_dimension_deltas(project_root, tmp_path) -> None:
    comparison = _module(project_root, "compare_frozen_pool_scores.py")
    baseline = tmp_path / "baseline.csv"
    calibrated = tmp_path / "calibrated.csv"
    fields = tuple(comparison.REQUIRED_COLUMNS)
    rows = [
        _row("pair-1", "cand_anchor", "Published Title", 2, 75),
        _row("pair-1", "cand_other", "Other Title", 1, 80),
    ]
    for path, reordered in ((baseline, rows), (calibrated, list(reversed(rows)))):
        with path.open("w", encoding="utf-8-sig", newline="") as output:
            writer = csv.DictWriter(output, fieldnames=fields)
            writer.writeheader()
            for row in reordered:
                writer.writerow(row)

    report = comparison.compare(baseline, calibrated)

    assert report["platform_title_coverage"]["baseline"]["hit_at_3"] == 1.0
    assert report["dimension_delta_calibrated_minus_baseline"]["semantic_fidelity"] == 0.0
    assert report["metric_definition"]["order_stability"].startswith("not measured")
