"""Evaluate generated titles against published platform-title weak positives.

The published title is a Platform Anchor / weak positive, not a quality ground
truth. This script measures reproducible title-recovery and candidate-pool
coverage metrics from the long CSV written by ``run_title_localization_batch``.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
from collections import defaultdict
from collections.abc import Iterable, Mapping
from pathlib import Path
from typing import Any

REQUIRED_COLUMNS = {
    "pair_id",
    "published_target_title",
    "status",
    "selected_title",
    "rank",
    "candidate_id",
    "candidate_title",
    "candidate_strategy",
    "candidate_prompt_version",
    "critical_violation_codes",
}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Evaluate platform-title coverage from a title-localization batch CSV."
    )
    parser.add_argument("--input", type=Path, required=True, help="batch result CSV")
    parser.add_argument("--report", type=Path, required=True, help="JSON metrics output")
    parser.add_argument(
        "--expected-candidates",
        type=int,
        default=12,
        help="expected unique candidates per successful record (default: 12)",
    )
    return parser


def normalize_title(title: str) -> str:
    """Normalize English titles for the documented exact-match metric."""

    return re.sub(r"[^a-z0-9]", "", title.lower())


def parse_critical_codes(value: str) -> list[str]:
    if not value.strip():
        return []
    parsed = json.loads(value)
    if not isinstance(parsed, list) or not all(isinstance(item, str) for item in parsed):
        raise ValueError("critical_violation_codes must be a JSON string array")
    return parsed


def load_rows(input_path: Path) -> list[dict[str, str]]:
    with input_path.open("r", encoding="utf-8-sig", newline="") as source:
        reader = csv.DictReader(source)
        columns = set(reader.fieldnames or ())
        missing = REQUIRED_COLUMNS - columns
        if missing:
            raise ValueError(f"input is missing required columns: {sorted(missing)}")
        return list(reader)


def successful_groups(rows: Iterable[dict[str, str]]) -> dict[str, list[dict[str, str]]]:
    grouped: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        if row["status"] == "success":
            grouped[row["pair_id"]].append(row)
    return dict(grouped)


def _rank(row: Mapping[str, str]) -> int:
    try:
        return int(row["rank"])
    except (KeyError, ValueError) as exc:
        raise ValueError(f"invalid rank for pair_id={row.get('pair_id', '')}") from exc


def evaluate(rows: list[dict[str, str]], expected_candidates: int) -> dict[str, Any]:
    if expected_candidates < 1:
        raise ValueError("expected_candidates must be positive")

    groups = successful_groups(rows)
    total_records = len({row["pair_id"] for row in rows})
    successes = len(groups)
    failures = total_records - successes
    if not successes:
        raise ValueError("input contains no successful records")

    top1_hits = hit_at_3 = hit_any = complete_records = 0
    matched_ranks: list[int] = []
    critical_candidates = 0
    records_with_critical = 0
    candidate_rows = 0
    strategy_hits: dict[str, int] = defaultdict(int)
    strategy_candidate_rows: dict[str, int] = defaultdict(int)
    prompt_versions: dict[str, int] = defaultdict(int)

    for pair_id, group in groups.items():
        anchor = normalize_title(group[0]["published_target_title"])
        if not anchor:
            raise ValueError(f"missing published_target_title for pair_id={pair_id}")
        selected = normalize_title(group[0]["selected_title"])
        matches = [row for row in group if normalize_title(row["candidate_title"]) == anchor]

        top1_hits += selected == anchor
        hit_at_3 += any(_rank(row) <= 3 for row in matches)
        hit_any += bool(matches)
        if matches:
            matched_ranks.append(min(_rank(row) for row in matches))
        if len({row["candidate_id"] for row in group}) == expected_candidates:
            complete_records += 1

        has_critical = False
        matched_strategies: set[str] = set()
        for row in group:
            strategy = row["candidate_strategy"]
            if not strategy:
                raise ValueError(f"missing candidate_strategy for pair_id={pair_id}")
            strategy_candidate_rows[strategy] += 1
            prompt_versions[row["candidate_prompt_version"]] += 1
            candidate_rows += 1
            codes = parse_critical_codes(row["critical_violation_codes"])
            critical_candidates += bool(codes)
            has_critical = has_critical or bool(codes)
            if normalize_title(row["candidate_title"]) == anchor:
                matched_strategies.add(strategy)
        records_with_critical += has_critical
        for strategy in matched_strategies:
            strategy_hits[strategy] += 1

    rate = lambda numerator, denominator: round(numerator / denominator, 6)
    strategies = sorted(strategy_candidate_rows)
    return {
        "metric_definition": {
            "exact_match_normalization": "lowercase and remove non-alphanumeric ASCII characters",
            "platform_title_interpretation": "Platform Anchor / weak positive, not title-quality ground truth",
        },
        "records": {
            "total": total_records,
            "successful": successes,
            "failed": failures,
            "candidate_complete": complete_records,
            "candidate_completeness_rate": rate(complete_records, successes),
        },
        "platform_title_coverage": {
            "top_1_agreement": rate(top1_hits, successes),
            "hit_at_3": rate(hit_at_3, successes),
            "hit_any": rate(hit_any, successes),
            "matched_records": hit_any,
            "mean_rank_when_hit": round(sum(matched_ranks) / len(matched_ranks), 6)
            if matched_ranks
            else None,
        },
        "critical_violations": {
            "candidate_count": candidate_rows,
            "candidates_with_critical_violation": critical_candidates,
            "candidate_rate": rate(critical_candidates, candidate_rows),
            "records_with_critical_violation": records_with_critical,
            "record_rate": rate(records_with_critical, successes),
        },
        "strategy_coverage": {
            strategy: {
                "candidate_rows": strategy_candidate_rows[strategy],
                "records_with_platform_title": strategy_hits[strategy],
                "record_hit_any": rate(strategy_hits[strategy], successes),
            }
            for strategy in strategies
        },
        "candidate_prompt_versions": dict(sorted(prompt_versions.items())),
    }


def sha256sum(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    args = build_parser().parse_args()
    try:
        report = evaluate(load_rows(args.input), args.expected_candidates)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"evaluation stopped: {exc}")
        return 2

    report["input"] = str(args.input)
    report["input_sha256"] = sha256sum(args.input)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
