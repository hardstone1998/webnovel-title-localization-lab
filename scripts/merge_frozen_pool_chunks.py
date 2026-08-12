"""Merge complete one-pool scoring chunks into a single stable CSV."""

from __future__ import annotations

import argparse
import csv
from pathlib import Path


def _index(path: Path) -> int:
    return int(path.stem.rsplit("_", 1)[1])


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Merge complete frozen-pool chunk CSV files.")
    parser.add_argument("--input-dir", type=Path, required=True)
    parser.add_argument("--label", required=True)
    parser.add_argument("--pool-count", type=int, default=69)
    parser.add_argument("--output", type=Path, required=True)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    chunks = sorted(args.input_dir.glob(f"pilot_remaining70_{args.label}_chunk_*.csv"), key=_index)
    rows: list[dict[str, str]] = []
    missing: list[int] = []
    fieldnames: list[str] | None = None
    for index in range(args.pool_count):
        path = args.input_dir / f"pilot_remaining70_{args.label}_chunk_{index:03d}.csv"
        if not path.exists():
            missing.append(index)
            continue
        with path.open(encoding="utf-8-sig", newline="") as source:
            reader = csv.DictReader(source)
            chunk_rows = list(reader)
            if len(chunk_rows) != 12 or len({row["candidate_id"] for row in chunk_rows}) != 12:
                missing.append(index)
                continue
            if fieldnames is None:
                fieldnames = list(reader.fieldnames or ())
            rows.extend(chunk_rows)
    if missing:
        raise ValueError(f"incomplete chunks for {args.label}: {missing}")
    if fieldnames is None:
        raise ValueError("no complete chunks found")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8-sig", newline="") as output:
        writer = csv.DictWriter(output, fieldnames=fieldnames, extrasaction="raise")
        writer.writeheader()
        writer.writerows(rows)
    print(f"merged {len(rows)} rows from {len(chunks)} chunks into {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
