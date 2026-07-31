"""Command-line entry point for the title-localization pipeline."""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence
from pathlib import Path

from .errors import LabError
from .orchestration import run_pipeline


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="title-localization",
        description="生成 12 个英文候选剧名，并通过八维加权评分选出最终剧名。",
    )
    parser.add_argument("--input", required=True, help="源记录 JSON 路径")
    parser.add_argument(
        "--config",
        default="configs/title_selection.default.json",
        help="工作流配置 JSON 路径",
    )
    parser.add_argument("--output-dir", required=True, help="制品输出目录")
    parser.add_argument(
        "--adapter",
        choices=("deterministic", "openai-compatible"),
        default="deterministic",
        help="模型适配器",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        outcome = run_pipeline(
            Path(args.input),
            Path(args.config),
            Path(args.output_dir),
            adapter_name=args.adapter,
        )
    except LabError as exc:
        print(json.dumps(exc.to_dict(), ensure_ascii=False), file=sys.stderr)
        return 2
    summary = {
        "outcome": outcome.ranking.outcome,
        "winner_candidate_id": outcome.ranking.winner_candidate_id,
        "candidate_artifact": str(outcome.candidate_path),
        "ranking_artifact": str(outcome.ranking_path),
        "report": str(outcome.report_path),
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0 if outcome.ranking.winner_candidate_id else 4


if __name__ == "__main__":
    raise SystemExit(main())
