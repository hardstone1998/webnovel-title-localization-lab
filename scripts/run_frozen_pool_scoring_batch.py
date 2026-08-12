"""Run resumable one-pool scoring chunks for one scoring configuration."""

from __future__ import annotations

import argparse
import csv
import subprocess
import sys
from pathlib import Path


def _complete_output(path: Path, expected_rows: int = 12) -> bool:
    if not path.exists():
        return False
    with path.open(encoding="utf-8-sig", newline="") as source:
        rows = list(csv.DictReader(source))
    return len(rows) == expected_rows and len({row["candidate_id"] for row in rows}) == expected_rows


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run resumable frozen-pool scoring chunks.")
    parser.add_argument("--input-csv", type=Path, required=True)
    parser.add_argument("--request-inputs", type=Path, required=True)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--label", required=True)
    parser.add_argument("--pool-count", type=int, default=69)
    parser.add_argument("--start", type=int, default=0, help="first complete-pool index to process")
    parser.add_argument(
        "--end",
        type=int,
        default=None,
        help="exclusive complete-pool index; defaults to --pool-count",
    )
    parser.add_argument("--permutation-seed", type=int, default=None)
    parser.add_argument("--adapter", choices=("openai-compatible", "deterministic"), default="openai-compatible")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    end = args.pool_count if args.end is None else args.end
    if args.pool_count < 1 or args.start < 0 or end <= args.start or end > args.pool_count:
        raise ValueError("invalid --pool-count, --start, or --end range")
    script = Path(__file__).with_name("rescore_frozen_candidate_pool.py")
    args.output_dir.mkdir(parents=True, exist_ok=True)
    for index in range(args.start, end):
        stem = f"pilot_remaining70_{args.label}_chunk_{index:03d}"
        output = args.output_dir / f"{stem}.csv"
        manifest = args.output_dir / f"{stem}.manifest.json"
        if _complete_output(output):
            print(f"[{index + 1}/{args.pool_count}] skip complete {output.name}", flush=True)
            continue
        command = [
            sys.executable,
            str(script),
            "--input-csv",
            str(args.input_csv),
            "--request-inputs",
            str(args.request_inputs),
            "--config",
            str(args.config),
            "--output",
            str(output),
            "--manifest",
            str(manifest),
            "--adapter",
            args.adapter,
            "--skip",
            str(index),
            "--limit",
            "1",
        ]
        if args.permutation_seed is not None:
            command.extend(("--permutation-seed", str(args.permutation_seed)))
        print(f"[{index + 1}/{args.pool_count}] score {output.name}", flush=True)
        subprocess.run(command, check=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
