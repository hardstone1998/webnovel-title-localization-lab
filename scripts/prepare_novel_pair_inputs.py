"""Create request-ready JSONL input from a novel-pair source JSONL file."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from app.utils.novel_pair_inputs import NovelPairInputError, convert_jsonl


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Convert author_zh, zh_synopsis, and genre_zh to request parameter JSONL."
    )
    parser.add_argument("--input", type=Path, required=True, help="source novel-pair JSONL path")
    parser.add_argument("--output", type=Path, required=True, help="request JSONL output path")
    parser.add_argument("--limit", type=int, help="optional number of non-empty records to convert")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    try:
        summary = convert_jsonl(args.input, args.output, limit=args.limit)
    except (OSError, NovelPairInputError) as exc:
        print(json.dumps({"error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 2
    print(json.dumps(summary.to_dict(), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
