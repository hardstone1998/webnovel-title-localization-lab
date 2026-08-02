"""Convert novel-pair JSONL records into request-ready input JSON objects."""

from __future__ import annotations

import json
from collections.abc import Iterable, Iterator, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

REQUEST_FIELDS = ("author_zh", "zh_synopsis", "genre_zh")


class NovelPairInputError(ValueError):
    """Raised when a JSONL record cannot be converted into a request input."""


@dataclass(frozen=True)
class ConversionSummary:
    """A concise result for a JSONL conversion run."""

    input_path: Path
    output_path: Path
    converted_count: int

    def to_dict(self) -> dict[str, str | int]:
        return {
            "input_path": str(self.input_path),
            "output_path": str(self.output_path),
            "converted_count": self.converted_count,
        }


def make_request_input(record: Mapping[str, Any]) -> dict[str, Any]:
    """Return the parameter JSON for one source record.

    ``pair_id`` is retained outside ``input`` so a batch response can be joined
    back to its source record without including unrelated source metadata.
    """

    pair_id = record.get("pair_id")
    if not isinstance(pair_id, str) or not pair_id.strip():
        raise NovelPairInputError("missing or invalid required field: pair_id")

    input_parameters: dict[str, str] = {}
    for field in REQUEST_FIELDS:
        value = record.get(field)
        if not isinstance(value, str) or not value.strip():
            raise NovelPairInputError(f"missing or invalid required field: {field}")
        input_parameters[field] = value

    return {"pair_id": pair_id, "input": input_parameters}


def iter_request_inputs(records: Iterable[Mapping[str, Any]]) -> Iterator[dict[str, Any]]:
    """Convert records to request inputs, adding their one-based record number to errors."""

    for record_number, record in enumerate(records, start=1):
        try:
            yield make_request_input(record)
        except NovelPairInputError as exc:
            raise NovelPairInputError(f"record {record_number}: {exc}") from exc


def convert_jsonl(
    input_path: Path,
    output_path: Path,
    *,
    limit: int | None = None,
) -> ConversionSummary:
    """Read a UTF-8 JSONL file and write one request JSON object per line."""

    if limit is not None and limit < 1:
        raise NovelPairInputError("limit must be a positive integer")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    converted_count = 0
    with (
        input_path.open("r", encoding="utf-8") as source,
        output_path.open("w", encoding="utf-8", newline="\n") as destination,
    ):
        for line_number, raw_line in enumerate(source, start=1):
            if not raw_line.strip():
                continue
            try:
                record = json.loads(raw_line)
            except json.JSONDecodeError as exc:
                raise NovelPairInputError(f"line {line_number}: invalid JSON ({exc.msg})") from exc
            if not isinstance(record, dict):
                raise NovelPairInputError(f"line {line_number}: JSON value must be an object")
            try:
                request_input = make_request_input(record)
            except NovelPairInputError as exc:
                raise NovelPairInputError(f"line {line_number}: {exc}") from exc

            destination.write(json.dumps(request_input, ensure_ascii=False) + "\n")
            converted_count += 1
            if limit is not None and converted_count >= limit:
                break

    return ConversionSummary(input_path, output_path, converted_count)
