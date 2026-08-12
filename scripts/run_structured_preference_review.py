"""Run a blind, resumable structured preference review for changed winners.

The input sheet intentionally contains no platform title.  Options are assigned
to A/B deterministically from the pair ID, so the reviewer cannot infer which
scoring prompt produced either title.  Each model response is checkpointed as
JSONL before the aggregate report is written.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any

from app.config.pipeline_config import load_config
from app.llm.adapters import OpenAICompatibleAdapter, create_adapter

VALID_CHOICES = {"A", "B", "tie"}
VALID_CONFIDENCES = {"high", "medium", "low"}


def _blind_options(row: dict[str, str]) -> tuple[dict[str, str], dict[str, str]]:
    """Return blinded A/B options and their V2/V3 provenance mapping."""

    v2 = {"title": row["option_a_title"], "origin": "v2"}
    v3 = {"title": row["option_b_title"], "origin": "v3"}
    swap = hashlib.sha256(row["pair_id"].encode("utf-8")).digest()[0] % 2 == 1
    first, second = (v3, v2) if swap else (v2, v3)
    return (
        {"A": first["title"], "B": second["title"]},
        {"A": first["origin"], "B": second["origin"]},
    )


def _prompt(row: dict[str, str], options: dict[str, str]) -> str:
    context = {
        "source_title": row["source_title"],
        "genre": row["genre"],
        "genre_zh": row["genre_zh"],
        "synopsis": row["synopsis"],
    }
    return """You are conducting a blind title-preference review for English web fiction.

You are NOT shown any platform title or model score. Judge only from the source
context and the two English title options. Prefer the title that is more faithful
to claims supported by the source, natural in English, appropriate to genre and
market, clear and memorable without clickbait or invented claims. Do not reward
a title merely for being more specific.

Return exactly one JSON object with this schema:
{
  "choice": "A" | "B" | "tie",
  "confidence": "high" | "medium" | "low",
  "rationale": "brief concrete explanation",
  "source_anchor_fidelity": {"A": 1-5, "B": 1-5},
  "natural_english": {"A": 1-5, "B": 1-5},
  "genre_tone_fit": {"A": 1-5, "B": 1-5},
  "market_title_function": {"A": 1-5, "B": 1-5},
  "factual_or_clickbait_issue": {"A": "none or brief issue", "B": "none or brief issue"}
}

Source context:
""" + json.dumps(context, ensure_ascii=False) + "\n\nOptions:\n" + json.dumps(options, ensure_ascii=False)


def _read_rows(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as source:
        return list(csv.DictReader(source))


def _existing(path: Path) -> dict[str, dict[str, Any]]:
    if not path.exists():
        return {}
    values: dict[str, dict[str, Any]] = {}
    with path.open(encoding="utf-8") as source:
        for line in source:
            if line.strip():
                value = json.loads(line)
                values[str(value["pair_id"])] = value
    return values


def _integer_scores(value: Any) -> dict[str, int]:
    if not isinstance(value, dict) or set(value) != {"A", "B"}:
        raise ValueError("dimension score must be an A/B object")
    result = {key: int(item) for key, item in value.items()}
    if any(score < 1 or score > 5 for score in result.values()):
        raise ValueError("dimension scores must be between 1 and 5")
    return result


def _review(adapter: OpenAICompatibleAdapter, row: dict[str, str]) -> dict[str, Any]:
    options, origin = _blind_options(row)
    value, metadata = adapter._request_json(_prompt(row, options), max_tokens=800)
    choice = str(value.get("choice", "")).strip()
    confidence = str(value.get("confidence", "")).strip()
    if choice not in VALID_CHOICES:
        raise ValueError(f"invalid review choice: {choice!r}")
    if confidence not in VALID_CONFIDENCES:
        raise ValueError(f"invalid review confidence: {confidence!r}")
    dimensions = {
        name: _integer_scores(value.get(name))
        for name in (
            "source_anchor_fidelity",
            "natural_english",
            "genre_tone_fit",
            "market_title_function",
        )
    }
    issues = value.get("factual_or_clickbait_issue")
    if not isinstance(issues, dict) or set(issues) != {"A", "B"}:
        raise ValueError("factual_or_clickbait_issue must be an A/B object")
    return {
        "pair_id": row["pair_id"],
        "options": options,
        "option_origins": origin,
        "choice": choice,
        "chosen_origin": origin.get(choice, "tie"),
        "confidence": confidence,
        "rationale": str(value.get("rationale", "")).strip(),
        "dimensions": dimensions,
        "factual_or_clickbait_issue": {key: str(item) for key, item in issues.items()},
        "provider_metadata": metadata,
    }


def _report(rows: list[dict[str, str]], results: dict[str, dict[str, Any]], args: argparse.Namespace) -> dict[str, Any]:
    choices = Counter(item["chosen_origin"] for item in results.values())
    confidence = Counter(item["confidence"] for item in results.values())
    return {
        "review_type": "blind-structured-model-preference-review",
        "reviewer_is_independent_of_scorer": False,
        "platform_titles_excluded_from_review_prompt": True,
        "input_review_rows": len(rows),
        "completed_reviews": len(results),
        "v2_preferred": choices["v2"],
        "v3_preferred": choices["v3"],
        "ties": choices["tie"],
        "confidence": dict(sorted(confidence.items())),
        "config": str(args.config),
        "model_adapter": args.adapter,
        "checkpoint": str(args.output),
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run blind structured V2/V3 preference reviews.")
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True, help="resumable JSONL checkpoint")
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--adapter", choices=("openai-compatible",), default="openai-compatible")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    if args.workers < 1:
        raise ValueError("--workers must be positive")
    rows = _read_rows(args.input)
    completed = _existing(args.output)
    pending = [row for row in rows if row["pair_id"] not in completed]
    config = load_config(args.config)
    adapter = create_adapter(args.adapter, config)
    if not isinstance(adapter, OpenAICompatibleAdapter):
        raise TypeError("structured review requires an OpenAI-compatible adapter")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("a", encoding="utf-8") as checkpoint, ThreadPoolExecutor(
        max_workers=args.workers
    ) as executor:
        futures = {executor.submit(_review, adapter, row): row["pair_id"] for row in pending}
        for future in as_completed(futures):
            result = future.result()
            checkpoint.write(json.dumps(result, ensure_ascii=False) + "\n")
            checkpoint.flush()
            completed[result["pair_id"]] = result
            print(f"reviewed {len(completed)}/{len(rows)} pair_id={result['pair_id']}")
    if len(completed) != len(rows):
        raise ValueError(f"review incomplete: expected {len(rows)}, got {len(completed)}")
    payload = _report(rows, completed, args)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
