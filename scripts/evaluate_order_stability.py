"""Measure winner agreement across frozen-pool scoring permutations."""

from __future__ import annotations

import argparse
import csv
import json
from collections import defaultdict
from pathlib import Path
from typing import Any


def _load(path: Path) -> dict[str, list[dict[str, str]]]:
    with path.open(encoding="utf-8-sig", newline="") as source:
        groups: dict[str, list[dict[str, str]]] = defaultdict(list)
        for row in csv.DictReader(source):
            groups[row["pair_id"]].append(row)
    return dict(groups)


def _winner(rows: list[dict[str, str]]) -> str:
    return min(rows, key=lambda row: int(row["rank"]))["candidate_id"]


def evaluate(paths: list[Path]) -> dict[str, Any]:
    runs = [_load(path) for path in paths]
    pair_ids = set.intersection(*(set(run) for run in runs))
    if not pair_ids:
        raise ValueError("runs have no shared candidate pools")
    unstable: list[dict[str, Any]] = []
    for pair_id in sorted(pair_ids):
        winners = [_winner(run[pair_id]) for run in runs]
        if len(set(winners)) > 1:
            unstable.append({"pair_id": pair_id, "winner_candidate_ids": winners})
    total = len(pair_ids)
    return {
        "runs": [str(path) for path in paths],
        "shared_candidate_pools": total,
        "stable_winner_pools": total - len(unstable),
        "winner_stability_rate": round((total - len(unstable)) / total, 6),
        "unstable_winner_pools": unstable,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Evaluate order stability from scoring CSV runs.")
    parser.add_argument("--inputs", nargs="+", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    report = evaluate(args.inputs)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
