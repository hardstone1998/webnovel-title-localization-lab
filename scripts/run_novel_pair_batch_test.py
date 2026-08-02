"""Validate a version-controlled novel-pair request JSONL batch."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from app.utils.novel_pair_inputs import (
    REQUEST_FIELDS,
    NovelPairInputError,
)

DEFAULT_INPUT = ROOT / "data/batch_tests/novel_pairs_100_request_inputs.jsonl"
DEFAULT_OUTPUT = ROOT / "data/batch_tests/novel_pairs_100_validation_output.jsonl"
DEFAULT_REPORT = ROOT / "data/batch_tests/novel_pairs_100_batch_test_report.json"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run conversion and checks for a novel-pair batch."
    )
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    return parser


def report_path(path: Path) -> str:
    """Prefer a portable project-relative path in committed batch reports."""

    try:
        return path.resolve().relative_to(ROOT).as_posix()
    except ValueError:
        return str(path)


def validate_input_and_write_output(input_path: Path, output_path: Path) -> int:
    pair_ids: set[str] = set()
    count = 0
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with (
        input_path.open("r", encoding="utf-8") as input_file,
        output_path.open("w", encoding="utf-8", newline="\n") as output_file,
    ):
        for line_number, raw_line in enumerate(input_file, start=1):
            if not raw_line.strip():
                continue
            payload = json.loads(raw_line)
            if set(payload) != {"pair_id", "input"}:
                raise NovelPairInputError(f"input line {line_number}: unexpected top-level keys")
            if not isinstance(payload["pair_id"], str) or not payload["pair_id"].strip():
                raise NovelPairInputError(f"input line {line_number}: invalid pair_id")
            if payload["pair_id"] in pair_ids:
                raise NovelPairInputError(f"input line {line_number}: duplicate pair_id")
            pair_ids.add(payload["pair_id"])
            if set(payload["input"]) != set(REQUEST_FIELDS):
                raise NovelPairInputError(f"input line {line_number}: incorrect input fields")
            if not all(isinstance(payload["input"][field], str) for field in REQUEST_FIELDS):
                raise NovelPairInputError(f"input line {line_number}: input fields must be strings")
            output_file.write(
                json.dumps({"pair_id": payload["pair_id"], "status": "passed"}, ensure_ascii=False)
                + "\n"
            )
            count += 1
    if count == 0:
        raise NovelPairInputError("input file contains no records")
    return count


def main() -> int:
    args = build_parser().parse_args()
    try:
        validated_count = validate_input_and_write_output(args.input, args.output)
    except (OSError, json.JSONDecodeError, NovelPairInputError) as exc:
        report = {"status": "failed", "error": str(exc)}
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(
            json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        print(json.dumps(report, ensure_ascii=False), file=sys.stderr)
        return 2

    report = {
        "status": "passed",
        "input_path": report_path(args.input),
        "output_path": report_path(args.output),
        "validated_count": validated_count,
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
