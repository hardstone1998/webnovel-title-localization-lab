"""Create a blind-ready structured review sheet for changed scoring winners."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

REVIEW_FIELDS = (
    "pair_id",
    "source_title",
    "genre",
    "genre_zh",
    "synopsis",
    "option_a_title",
    "option_a_score",
    "option_b_title",
    "option_b_score",
    "platform_anchor_present_in_pool",
    "reviewer_choice",
    "choice_confidence",
    "source_anchor_fidelity",
    "natural_english",
    "genre_tone_fit",
    "market_title_function",
    "factual_or_clickbait_issue",
    "review_notes",
)


def _rows(path: Path) -> dict[str, list[dict[str, str]]]:
    groups: dict[str, list[dict[str, str]]] = {}
    with path.open(encoding="utf-8-sig", newline="") as source:
        for row in csv.DictReader(source):
            groups.setdefault(row["pair_id"], []).append(row)
    return groups


def _winner(rows: list[dict[str, str]]) -> dict[str, str]:
    return min(rows, key=lambda row: int(row["rank"]))


def _synopses(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    with path.open(encoding="utf-8") as source:
        for line in source:
            if line.strip():
                row = json.loads(line)
                values[str(row["pair_id"])] = str(row["zh_synopsis"])
    return values


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Prepare a structured winner-preference review CSV.")
    parser.add_argument("--baseline", type=Path, required=True)
    parser.add_argument("--calibrated", type=Path, required=True)
    parser.add_argument("--request-inputs", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    baseline = _rows(args.baseline)
    calibrated = _rows(args.calibrated)
    synopses = _synopses(args.request_inputs)
    if set(baseline) != set(calibrated):
        raise ValueError("baseline and calibrated inputs must contain the same pair IDs")
    review_rows: list[dict[str, str]] = []
    for pair_id in sorted(baseline):
        old = _winner(baseline[pair_id])
        new = _winner(calibrated[pair_id])
        if old["candidate_id"] == new["candidate_id"]:
            continue
        first = baseline[pair_id][0]
        anchor = first["published_target_title"]
        review_rows.append(
            {
                "pair_id": pair_id,
                "source_title": first["source_title"],
                "genre": first["genre"],
                "genre_zh": first["genre_zh"],
                "synopsis": synopses[pair_id],
                "option_a_title": old["candidate_title"],
                "option_a_score": old["candidate_total_score"],
                "option_b_title": new["candidate_title"],
                "option_b_score": new["candidate_total_score"],
                "platform_anchor_present_in_pool": str(
                    any(row["candidate_title"].casefold() == anchor.casefold() for row in baseline[pair_id])
                ).lower(),
                "reviewer_choice": "",
                "choice_confidence": "",
                "source_anchor_fidelity": "",
                "natural_english": "",
                "genre_tone_fit": "",
                "market_title_function": "",
                "factual_or_clickbait_issue": "",
                "review_notes": "",
            }
        )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8-sig", newline="") as output:
        writer = csv.DictWriter(output, fieldnames=REVIEW_FIELDS)
        writer.writeheader()
        writer.writerows(review_rows)
    print(f"prepared {len(review_rows)} changed-winner review rows at {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
