from __future__ import annotations

import json

import pytest
from app.utils.novel_pair_inputs import (
    NovelPairInputError,
    convert_jsonl,
    make_request_input,
)


def test_make_request_input_keeps_only_pair_id_and_requested_parameters() -> None:
    record = {
        "pair_id": "pair-001",
        "author_zh": "作者",
        "zh_synopsis": "简介",
        "genre_zh": "玄幻",
        "zh_title": "不应输出",
    }

    assert make_request_input(record) == {
        "pair_id": "pair-001",
        "input": {"author_zh": "作者", "zh_synopsis": "简介", "genre_zh": "玄幻"},
    }


@pytest.mark.parametrize("field", ("pair_id", "author_zh", "zh_synopsis", "genre_zh"))
def test_make_request_input_rejects_missing_required_fields(field: str) -> None:
    record = {
        "pair_id": "pair-001",
        "author_zh": "作者",
        "zh_synopsis": "简介",
        "genre_zh": "玄幻",
    }
    record.pop(field)

    with pytest.raises(NovelPairInputError, match=field):
        make_request_input(record)


def test_convert_jsonl_writes_utf8_request_jsonl(tmp_path) -> None:
    source = tmp_path / "source.jsonl"
    destination = tmp_path / "request.jsonl"
    source.write_text(
        json.dumps(
            {"pair_id": "one", "author_zh": "甲", "zh_synopsis": "乙", "genre_zh": "丙"},
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )

    summary = convert_jsonl(source, destination)

    assert summary.converted_count == 1
    assert json.loads(destination.read_text(encoding="utf-8")) == {
        "pair_id": "one",
        "input": {"author_zh": "甲", "zh_synopsis": "乙", "genre_zh": "丙"},
    }
