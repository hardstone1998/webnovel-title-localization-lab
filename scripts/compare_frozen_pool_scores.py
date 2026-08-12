"""Compare two scoring runs over the same frozen candidate pool."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
from collections import defaultdict
from pathlib import Path
from typing import Any

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
REQUIRED_COLUMNS = {
    "pair_id",
    "published_target_title",
    "scoring_prompt_version",
    "rank",
    "candidate_id",
    "candidate_title",
    "candidate_total_score",
    *DIMENSIONS,
}


def _normalize(title: str) -> str:
    return re.sub(r"[^a-z0-9]", "", title.lower())


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _load(path: Path) -> dict[str, list[dict[str, str]]]:
    with path.open(encoding="utf-8-sig", newline="") as source:
        reader = csv.DictReader(source)
        missing = REQUIRED_COLUMNS - set(reader.fieldnames or ())
        if missing:
            raise ValueError(f"{path}: missing required columns {sorted(missing)}")
        groups: dict[str, list[dict[str, str]]] = defaultdict(list)
        for row in reader:
            if row.get("status", "success") == "success":
                groups[row["pair_id"]].append(row)
    if not groups:
        raise ValueError(f"{path}: no successful rows")
    return dict(groups)


def _rank(row: dict[str, str]) -> int:
    return int(row["rank"])


def _versions(groups: dict[str, list[dict[str, str]]]) -> list[str]:
    return sorted({row["scoring_prompt_version"] for rows in groups.values() for row in rows})


def _coverage(groups: dict[str, list[dict[str, str]]]) -> dict[str, Any]:
    top1 = hit3 = hit_any = 0
    ranks: list[int] = []
    for rows in groups.values():
        anchor = _normalize(rows[0]["published_target_title"])
        matches = [row for row in rows if _normalize(row["candidate_title"]) == anchor]
        hit_any += bool(matches)
        hit3 += any(_rank(row) <= 3 for row in matches)
        top1 += any(_rank(row) == 1 for row in matches)
        if matches:
            ranks.append(min(_rank(row) for row in matches))
    total = len(groups)
    return {
        "records": total,
        "top_1_agreement": round(top1 / total, 6),
        "hit_at_3": round(hit3 / total, 6),
        "hit_any": round(hit_any / total, 6),
        "matched_records": hit_any,
        "mean_rank_when_hit": round(sum(ranks) / len(ranks), 6) if ranks else None,
    }


def compare(baseline: Path, calibrated: Path) -> dict[str, Any]:
    left = _load(baseline)
    right = _load(calibrated)
    if set(left) != set(right):
        raise ValueError("the two score files do not contain the same pair_id set")

    dimension_deltas: dict[str, list[int]] = defaultdict(list)
    rank_deltas: list[int] = []
    changed_winners = 0
    exact_anchor_cases: list[dict[str, Any]] = []
    for pair_id in sorted(left):
        left_by_id = {row["candidate_id"]: row for row in left[pair_id]}
        right_by_id = {row["candidate_id"]: row for row in right[pair_id]}
        if set(left_by_id) != set(right_by_id):
            raise ValueError(f"pair_id={pair_id}: candidate IDs differ between runs")
        left_winner = min(left[pair_id], key=_rank)["candidate_id"]
        right_winner = min(right[pair_id], key=_rank)["candidate_id"]
        changed_winners += left_winner != right_winner
        anchor = _normalize(left[pair_id][0]["published_target_title"])
        for candidate_id, old in left_by_id.items():
            new = right_by_id[candidate_id]
            rank_deltas.append(_rank(old) - _rank(new))
            for dimension in DIMENSIONS:
                dimension_deltas[dimension].append(int(new[dimension]) - int(old[dimension]))
            if _normalize(old["candidate_title"]) == anchor:
                exact_anchor_cases.append(
                    {
                        "pair_id": pair_id,
                        "title": old["candidate_title"],
                        "baseline_rank": _rank(old),
                        "calibrated_rank": _rank(new),
                        "baseline_score": float(old["candidate_total_score"]),
                        "calibrated_score": float(new["candidate_total_score"]),
                    }
                )
    return {
        "metric_definition": {
            "platform_title_interpretation": "Platform Anchor / weak positive, not title-quality ground truth",
            "candidate_pool": "candidate IDs must be identical in baseline and calibrated runs",
            "order_stability": "not measured by this two-run comparison; requires repeated rescoring with permuted candidate order",
            "human_or_structured_review": "not collected by this script; required before changing the default configuration",
        },
        "inputs": {
            "baseline": str(baseline),
            "baseline_sha256": _sha256(baseline),
            "baseline_scoring_prompt_versions": _versions(left),
            "calibrated": str(calibrated),
            "calibrated_sha256": _sha256(calibrated),
            "calibrated_scoring_prompt_versions": _versions(right),
        },
        "platform_title_coverage": {"baseline": _coverage(left), "calibrated": _coverage(right)},
        "ranking_change": {
            "records_with_changed_winner": changed_winners,
            "winner_change_rate": round(changed_winners / len(left), 6),
            "mean_rank_improvement_per_candidate": round(sum(rank_deltas) / len(rank_deltas), 6),
        },
        "dimension_delta_calibrated_minus_baseline": {
            dimension: round(sum(values) / len(values), 6)
            for dimension, values in dimension_deltas.items()
        },
        "exact_platform_title_candidates": exact_anchor_cases,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Compare frozen-pool scoring CSV files.")
    parser.add_argument("--baseline", type=Path, required=True)
    parser.add_argument("--calibrated", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    report = compare(args.baseline, args.calibrated)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
