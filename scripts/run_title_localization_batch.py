"""Call the title-localization API for every record in a novel-pairs JSONL file.

Each successful API response is flattened to one CSV row per ranked candidate.
This keeps the selected result and all eight scoring dimensions available for
analysis without embedding JSON inside a spreadsheet cell.  Failed requests
also produce one row, so a completed CSV is still useful for retrying failures.
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
import time
from collections.abc import Iterable, Iterator, Mapping
from concurrent.futures import ThreadPoolExecutor
from functools import partial
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
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
CSV_FIELDS = (
    "pair_id",
    "sample_id",
    "source_title",
    "published_target_title",
    "genre",
    "genre_zh",
    "status",
    "http_status",
    "error",
    "selected_candidate_id",
    "selected_title",
    "selected_score",
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


class BatchInputError(ValueError):
    """Raised when a source record cannot be converted to an API payload."""


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run a JSONL novel-pair batch through /v1/title-localizations."
    )
    parser.add_argument("--input", type=Path, required=True, help="source JSONL file")
    parser.add_argument("--output", type=Path, required=True, help="result CSV file")
    parser.add_argument(
        "--endpoint",
        default="http://127.0.0.1:8000/v1/title-localizations",
        help="title-localization API endpoint",
    )
    parser.add_argument("--timeout", type=float, default=180.0, help="per-request timeout in seconds")
    parser.add_argument("--retries", type=int, default=1, help="retries after the first attempt")
    parser.add_argument(
        "--workers",
        type=int,
        default=4,
        help="number of concurrent API requests (default: 4)",
    )
    parser.add_argument(
        "--skip",
        type=int,
        default=0,
        help="number of source records to skip; useful for resuming an interrupted batch",
    )
    parser.add_argument(
        "--append",
        action="store_true",
        help="append rows to an existing CSV instead of replacing it (use with --skip)",
    )
    parser.add_argument(
        "--pause", type=float, default=0.0, help="seconds to wait after each request"
    )
    return parser


def required_string(record: Mapping[str, Any], field: str) -> str:
    value = record.get(field)
    if not isinstance(value, str) or not value.strip():
        raise BatchInputError(f"missing or invalid required field: {field}")
    return value.strip()


def payload_from_record(record: Mapping[str, Any]) -> dict[str, Any]:
    """Map a novel-pair record to the API's documented request contract."""

    pair_id = required_string(record, "pair_id")
    source_title = required_string(record, "zh_title")
    genre = required_string(record, "genre_en")
    genre_zh = required_string(record, "genre_zh")
    synopsis = required_string(record, "zh_synopsis")
    published_title = required_string(record, "en_title")

    metadata: dict[str, Any] = {"published_en_title": published_title}
    for source_field, metadata_field in (
        ("author_zh", "author"),
        ("chapter_count_zh", "chapter_count"),
        ("qidian_book_id", "qidian_book_id"),
        ("webnovel_book_id", "webnovel_book_id"),
    ):
        if record.get(source_field) is not None:
            metadata[metadata_field] = record[source_field]

    return {
        "source": {
            "sample_id": pair_id,
            "source_title": source_title,
            "source_language": "zh-CN",
            "target_language": "en-US",
            "genre": genre,
            "genre_zh": genre_zh,
            "synopsis": synopsis,
            "published_target_title": published_title,
            "metadata": metadata,
        },
        "debug": True,
    }


def post_json(endpoint: str, payload: Mapping[str, Any], timeout: float) -> tuple[int, dict[str, Any]]:
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    request = Request(
        endpoint,
        data=body,
        headers={"Content-Type": "application/json; charset=utf-8"},
        method="POST",
    )
    try:
        with urlopen(request, timeout=timeout) as response:
            status = response.status
            raw_response = response.read().decode("utf-8")
    except HTTPError as exc:
        raw_response = exc.read().decode("utf-8", errors="replace")
        try:
            return exc.code, json.loads(raw_response)
        except json.JSONDecodeError:
            return exc.code, {"error": raw_response}
    return status, json.loads(raw_response)


def request_result(
    endpoint: str, payload: Mapping[str, Any], timeout: float, retries: int
) -> tuple[int | None, dict[str, Any], str]:
    """Request once plus retries, returning an error string instead of raising."""

    for attempt in range(retries + 1):
        try:
            status, response = post_json(endpoint, payload, timeout)
            if 200 <= status < 300:
                return status, response, ""
            error = json.dumps(response, ensure_ascii=False)
        except (HTTPError, URLError, TimeoutError, json.JSONDecodeError, OSError) as exc:
            status = None
            response = {}
            error = str(exc)
        if attempt < retries:
            time.sleep(min(2**attempt, 5))
    return status, response, error


def input_context(record: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "pair_id": str(record.get("pair_id", "")),
        "sample_id": str(record.get("pair_id", "")),
        "source_title": str(record.get("zh_title", "")),
        "published_target_title": str(record.get("en_title", "")),
        "genre": str(record.get("genre_en", "")),
        "genre_zh": str(record.get("genre_zh", "")),
    }


def rows_from_response(record: Mapping[str, Any], response: Mapping[str, Any]) -> Iterator[dict[str, Any]]:
    selected = response.get("selected")
    ranked_titles = response.get("ranked_titles")
    if not isinstance(selected, Mapping) or not isinstance(ranked_titles, list):
        raise TypeError("successful response is missing selected or ranked_titles")

    base = input_context(record) | {
        "status": "success",
        "http_status": 200,
        "error": "",
        "selected_candidate_id": selected.get("candidate_id", ""),
        "selected_title": selected.get("title", ""),
        "selected_score": selected.get("score", ""),
    }
    for ranked in ranked_titles:
        if not isinstance(ranked, Mapping):
            raise TypeError("ranked_titles contains a non-object item")
        dimensions = ranked.get("dimensions", {})
        if not isinstance(dimensions, Mapping):
            raise TypeError("ranked title dimensions is not an object")
        yield base | {
            "rank": ranked.get("rank", ""),
            "candidate_id": ranked.get("candidate_id", ""),
            "candidate_title": ranked.get("title", ""),
            "candidate_strategy": ranked.get("strategy", ""),
            "candidate_ordinal": ranked.get("ordinal", ""),
            "candidate_prompt_version": ranked.get("prompt_version", ""),
            "candidate_total_score": ranked.get("total_score", ""),
            "critical_violation_codes": json.dumps(
                ranked.get("critical_violation_codes", []), ensure_ascii=False
            ),
            **{dimension: dimensions.get(dimension, "") for dimension in DIMENSIONS},
        }


def failure_row(record: Mapping[str, Any], status: int | None, error: str) -> dict[str, Any]:
    return input_context(record) | {
        "status": "failed",
        "http_status": status or "",
        "error": error,
        "selected_candidate_id": "",
        "selected_title": "",
        "selected_score": "",
        "rank": "",
        "candidate_id": "",
        "candidate_title": "",
        "candidate_strategy": "",
        "candidate_ordinal": "",
        "candidate_prompt_version": "",
        "candidate_total_score": "",
        "critical_violation_codes": "",
        **{dimension: "" for dimension in DIMENSIONS},
    }


def run_record(
    item: tuple[int, dict[str, Any]],
    *,
    endpoint: str,
    timeout: float,
    retries: int,
) -> tuple[int, list[dict[str, Any]], bool, str]:
    """Run one record and turn both API and conversion errors into CSV rows."""

    line_number, record = item
    try:
        payload = payload_from_record(record)
        http_status, response, error = request_result(endpoint, payload, timeout, retries)
        if error:
            return line_number, [failure_row(record, http_status, error)], False, error
        response_rows = list(rows_from_response(record, response))
        if not response_rows:
            raise ValueError("successful response has no ranked titles")
        return line_number, response_rows, True, ""
    except (BatchInputError, TypeError, ValueError) as exc:
        return line_number, [failure_row(record, None, str(exc))], False, str(exc)


def iter_records(input_path: Path) -> Iterable[tuple[int, dict[str, Any]]]:
    with input_path.open("r", encoding="utf-8") as source:
        for line_number, line in enumerate(source, start=1):
            if not line.strip():
                continue
            value = json.loads(line)
            if not isinstance(value, dict):
                raise BatchInputError(f"line {line_number}: JSON value must be an object")
            yield line_number, value


def main() -> int:
    args = build_parser().parse_args()
    if (
        args.timeout <= 0
        or args.retries < 0
        or args.pause < 0
        or args.workers < 1
        or args.skip < 0
    ):
        print(
            "--timeout must be > 0; --retries, --pause, and --skip must be >= 0; "
            "--workers must be >= 1",
            file=sys.stderr,
        )
        return 2

    try:
        records = list(iter_records(args.input))[args.skip :]
    except (OSError, json.JSONDecodeError, BatchInputError) as exc:
        print(f"batch stopped: {exc}", file=sys.stderr)
        return 2

    args.output.parent.mkdir(parents=True, exist_ok=True)
    total = successful = failed = 0
    append_to_existing = args.append and args.output.exists() and args.output.stat().st_size > 0
    mode = "a" if append_to_existing else "w"
    encoding = "utf-8" if append_to_existing else "utf-8-sig"
    with args.output.open(mode, encoding=encoding, newline="") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=CSV_FIELDS, extrasaction="raise")
        if not append_to_existing:
            writer.writeheader()
        worker = partial(
            run_record,
            endpoint=args.endpoint,
            timeout=args.timeout,
            retries=args.retries,
        )
        with ThreadPoolExecutor(max_workers=args.workers) as executor:
            # executor.map preserves input order, making the resulting CSV stable.
            for total, (line_number, rows, succeeded, error) in enumerate(
                executor.map(worker, records), start=1
            ):
                writer.writerows(rows)
                csv_file.flush()
                if succeeded:
                    successful += 1
                    print(f"[{total}/{len(records)}] line {line_number}: success", flush=True)
                else:
                    failed += 1
                    print(
                        f"[{total}/{len(records)}] line {line_number}: failed ({error})",
                        file=sys.stderr,
                        flush=True,
                    )
                if args.pause:
                    time.sleep(args.pause)

    print(
        json.dumps(
            {
                "input": str(args.input),
                "output": str(args.output),
                "total": total,
                "successful": successful,
                "failed": failed,
                "workers": args.workers,
            },
            ensure_ascii=False,
        )
    )
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
