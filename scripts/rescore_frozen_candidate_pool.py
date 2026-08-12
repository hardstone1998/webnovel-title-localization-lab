"""Rescore a fixed title-candidate pool without rerunning generation.

The input CSV is the long-form batch export from ``run_title_localization_batch``.
Each successful ``pair_id`` must contain one immutable row per candidate.  This
script rebuilds a ``CandidateSet`` solely to reuse the production ranker, then
writes a fresh long-form score CSV and a public provenance manifest.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
from collections import defaultdict
from collections.abc import Iterable
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path

from app.config.pipeline_config import load_config
from app.domain.contracts import (
    Candidate,
    CandidateProvenance,
    CandidateSet,
    SourceRecord,
    fingerprint,
)
from app.llm.adapters import create_adapter
from app.pipeline.scoring import TitleRanker
from app.validators.validation import validate_ranking_result

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
    "source_title",
    "published_target_title",
    "genre",
    "genre_zh",
    "status",
    "candidate_id",
    "candidate_title",
    "candidate_strategy",
    "candidate_ordinal",
    "candidate_prompt_version",
}
CSV_FIELDS = (
    "pair_id",
    "source_title",
    "published_target_title",
    "genre",
    "genre_zh",
    "status",
    "scoring_prompt_version",
    "rank",
    "candidate_id",
    "candidate_title",
    "candidate_strategy",
    "candidate_ordinal",
    "candidate_prompt_version",
    "candidate_total_score",
    "critical_violation_codes",
    *DIMENSIONS,
)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _int(value: str, field: str, pair_id: str) -> int:
    try:
        return int(value)
    except ValueError as exc:
        raise ValueError(f"pair_id={pair_id}: invalid {field}={value!r}") from exc


def _load_rows(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as source:
        reader = csv.DictReader(source)
        missing = REQUIRED_COLUMNS - set(reader.fieldnames or ())
        if missing:
            raise ValueError(f"input is missing required columns: {sorted(missing)}")
        return list(reader)


def _groups(rows: Iterable[dict[str, str]]) -> dict[str, list[dict[str, str]]]:
    grouped: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        if row["status"] == "success":
            grouped[row["pair_id"]].append(row)
    if not grouped:
        raise ValueError("input contains no successful candidate pools")
    return dict(grouped)


def _source(rows: list[dict[str, str]]) -> SourceRecord:
    first = rows[0]
    if any(
        row[key] != first[key]
        for row in rows
        for key in ("source_title", "published_target_title", "genre", "genre_zh")
    ):
        raise ValueError(f"pair_id={first['pair_id']}: inconsistent source fields")
    return SourceRecord.from_dict(
        {
            "sample_id": first["pair_id"],
            "source_title": first["source_title"],
            "source_language": "zh-CN",
            "target_language": "en-US",
            "genre": first["genre"],
            "genre_zh": first["genre_zh"],
            # The prior scoring run has no synopsis in its CSV.  Callers must
            # enrich it from request JSONL before a real rescore.
            "synopsis": first.get("synopsis", ""),
            "published_target_title": first["published_target_title"],
        }
    )


def _candidate_set(rows: list[dict[str, str]], input_sha256: str) -> CandidateSet:
    first = rows[0]
    candidates = tuple(
        Candidate(
            candidate_id=row["candidate_id"],
            title=row["candidate_title"],
            normalized_title=row["candidate_title"].casefold(),
            strategy=row["candidate_strategy"],
            ordinal=_int(row["candidate_ordinal"], "candidate_ordinal", first["pair_id"]),
            provenance=CandidateProvenance(
                model_id="frozen-candidate-pool",
                prompt_version=row["candidate_prompt_version"],
                parameters={"frozen_pool_sha256": input_sha256},
                attempt=1,
            ),
        )
        for row in rows
    )
    if len({candidate.candidate_id for candidate in candidates}) != len(candidates):
        raise ValueError(f"pair_id={first['pair_id']}: duplicate candidate_id")
    payload = {"pair_id": first["pair_id"], "candidate_ids": [item.candidate_id for item in candidates]}
    return CandidateSet(
        schema_version="1.0",
        candidate_set_id=f"frozen_{fingerprint(payload)[:16]}",
        sample_id=first["pair_id"],
        source_fingerprint="from-batch-csv",
        created_at="1970-01-01T00:00:00+00:00",
        generation_config={"frozen_pool_sha256": input_sha256},
        attempts={"source_title": 0, "synopsis": 0, "market_localized": 0},
        candidates=candidates,
    )


def _synopses(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    with path.open(encoding="utf-8") as source:
        for line_number, line in enumerate(source, start=1):
            if not line.strip():
                continue
            record = json.loads(line)
            pair_id = str(record.get("pair_id", ""))
            synopsis = str(record.get("zh_synopsis", ""))
            if not pair_id or not synopsis:
                raise ValueError(f"request input line {line_number} lacks pair_id or zh_synopsis")
            values[pair_id] = synopsis
    return values


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Rescore a frozen title candidate pool.")
    parser.add_argument("--input-csv", type=Path, required=True)
    parser.add_argument("--request-inputs", type=Path, required=True)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument(
        "--expected-candidates",
        type=int,
        default=12,
        help="rescore only pools with this exact candidate count (default: 12)",
    )
    parser.add_argument(
        "--skip",
        type=int,
        default=0,
        help="skip this many complete pools in stable input order",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=0,
        help="score at most this many complete pools; 0 means all",
    )
    parser.add_argument(
        "--permutation-seed",
        type=int,
        default=None,
        help="override the configured candidate-order permutation seed",
    )
    parser.add_argument(
        "--adapter",
        choices=("openai-compatible", "deterministic"),
        default="openai-compatible",
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()
    rows = _load_rows(args.input_csv)
    groups = _groups(rows)
    if args.expected_candidates < 1 or args.skip < 0 or args.limit < 0:
        raise ValueError("--expected-candidates must be positive; --skip and --limit must be non-negative")
    complete_groups = {
        pair_id: group
        for pair_id, group in groups.items()
        if len({row["candidate_id"] for row in group}) == args.expected_candidates
    }
    skipped_pools = {
        pair_id: len({row["candidate_id"] for row in group})
        for pair_id, group in groups.items()
        if pair_id not in complete_groups
    }
    if not complete_groups:
        raise ValueError("input contains no complete candidate pools")
    selected_items = list(complete_groups.items())[args.skip :]
    if args.limit:
        selected_items = selected_items[: args.limit]
    if not selected_items:
        raise ValueError("selected complete-pool range is empty")
    input_sha256 = _sha256(args.input_csv)
    synopses = _synopses(args.request_inputs)
    config = load_config(args.config)
    if args.permutation_seed is not None:
        config = replace(
            config,
            scoring=replace(config.scoring, permutation_seed=args.permutation_seed),
        )
    adapter = create_adapter(args.adapter, config)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    temporary_output = args.output.with_name(f"{args.output.name}.{os.getpid()}.tmp")
    with temporary_output.open("w", encoding="utf-8-sig", newline="") as output:
        writer = csv.DictWriter(output, fieldnames=CSV_FIELDS, extrasaction="raise")
        writer.writeheader()
        for pair_id, group in selected_items:
            if pair_id not in synopses:
                raise ValueError(f"pair_id={pair_id}: missing request input synopsis")
            group = [dict(row, synopsis=synopses[pair_id]) for row in group]
            source = _source(group)
            candidate_set = _candidate_set(group, input_sha256)
            ranking = TitleRanker(adapter, config.scoring).rank(
                source,
                candidate_set,
                fingerprint(candidate_set.to_dict()),
            )
            validate_ranking_result(ranking, candidate_set)
            by_id = {item.candidate_id: item for item in ranking.scores}
            candidates = {item.candidate_id: item for item in candidate_set.candidates}
            for rank, candidate_id in enumerate(ranking.ordered_candidate_ids, start=1):
                score = by_id[candidate_id]
                candidate = candidates[candidate_id]
                writer.writerow(
                    {
                        "pair_id": pair_id,
                        "source_title": source.source_title,
                        "published_target_title": source.published_target_title,
                        "genre": source.genre,
                        "genre_zh": source.genre_zh,
                        "status": "success",
                        "scoring_prompt_version": config.scoring.prompt_version,
                        "rank": rank,
                        "candidate_id": candidate_id,
                        "candidate_title": candidate.title,
                        "candidate_strategy": candidate.strategy,
                        "candidate_ordinal": candidate.ordinal,
                        "candidate_prompt_version": candidate.provenance.prompt_version,
                        "candidate_total_score": score.authoritative_total,
                        "critical_violation_codes": json.dumps(
                            [item.code for item in score.violations if item.severity == "critical"],
                            ensure_ascii=False,
                        ),
                        **{name: score.dimensions[name].score for name in DIMENSIONS},
                    }
                )
    temporary_output.replace(args.output)
    manifest = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "input_csv": str(args.input_csv),
        "input_csv_sha256": input_sha256,
        "request_inputs": str(args.request_inputs),
        "request_inputs_sha256": _sha256(args.request_inputs),
        "output": str(args.output),
        "config": str(args.config),
        "scoring_prompt_version": config.scoring.prompt_version,
        "permutation_seed": config.scoring.permutation_seed,
        "complete_candidate_pool_count": len(complete_groups),
        "candidate_pool_count": len(selected_items),
        "skip": args.skip,
        "limit": args.limit,
        "expected_candidates": args.expected_candidates,
        "skipped_incomplete_pools": skipped_pools,
        "adapter": args.adapter,
    }
    args.manifest.parent.mkdir(parents=True, exist_ok=True)
    args.manifest.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(manifest, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
