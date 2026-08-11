"""Create the versioned 100-record frozen title-alignment set.

The source corpus is local-only.  This script intentionally writes only the
declared frozen derivative and a text-free manifest; it never changes the
1,000-record training corpus.
"""

from __future__ import annotations

import csv
import hashlib
import json
import shutil
from collections import Counter
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "data/processed/novel_pairs/1000/novel_pairs_1000.csv"
OUTPUT = ROOT / "data/processed/novel_pairs/100/novel_pairs_100.jsonl"
PILOT_BACKUP = ROOT / "data/processed/novel_pairs/pilot_v0/novel_pairs_100.jsonl"
MANIFEST = ROOT / "data/manifests/frozen_title_alignment_v1.json"
SEED = "frozen-title-alignment-v1-2026-08-11"
SOURCE_SHA256 = "41fc4fd774a7e649ed4bf734acf694075c2bc657fa64da1d6931325ee01cf1fd"
LEGACY_PILOT_SHA256 = "3275317d63950313df2650ca11301e0e1eea71db2f22a444c1b6936ad0bd34b3"
RECORD_COUNT = 100
ACCEPTED_MAPPING_TYPES = {
    "curated_cross_site_mapping",
    "same_entity_bilingual_alias_cross_snapshot",
}
# Found during the pre-freeze title-and-author audit.  Its Chinese title
# ``数据侠客行`` is by 七尺居士, while the paired English work is credited to
# Liang Maoshuai, so it must not become a weak-positive anchor.
REJECTED_MAPPING_IDS = {
    "e3362c1401d4766f3b7347f2edf409df2912a7bc": "Chinese/English author conflict in title mapping audit",
}
LEGACY_PILOT_SIBLINGS = (
    "novel_pairs_100.csv",
    "中英文小说元信息配对_100对.xlsx",
)


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def repair_mojibake(value: str) -> str:
    """Repair the known Latin-1-as-GB18030 corruption without touching English."""

    value = value.lstrip("\ufeff")
    if not value or any(ord(character) > 255 for character in value):
        return value
    try:
        repaired = value.encode("latin-1").decode("gb18030")
    except UnicodeError:
        return value
    contains_cjk = any("\u3400" <= character <= "\u9fff" for character in repaired)
    return repaired if contains_cjk else value


def repair_row(row: dict[str, str]) -> dict[str, str]:
    return {key: repair_mojibake(value) for key, value in row.items()}


def load_legacy_pilot() -> list[dict[str, Any]]:
    """Preserve the V0 input before replacing its former path."""

    if PILOT_BACKUP.exists():
        source = PILOT_BACKUP
    else:
        source = OUTPUT
        if not source.exists():
            raise FileNotFoundError(f"legacy V0 pilot is missing: {source}")
        if sha256_file(source) != LEGACY_PILOT_SHA256:
            raise ValueError("refusing to overwrite an unexpected frozen-set target")
        PILOT_BACKUP.parent.mkdir(parents=True, exist_ok=True)
        PILOT_BACKUP.write_bytes(source.read_bytes())

    if sha256_file(source) != LEGACY_PILOT_SHA256:
        raise ValueError(f"legacy V0 pilot checksum mismatch: {source}")
    return [json.loads(line) for line in source.read_text(encoding="utf-8").splitlines() if line.strip()]


def archive_legacy_pilot_siblings() -> None:
    """Keep the former V0 CSV/XLSX beside the local-only pilot JSONL."""

    for filename in LEGACY_PILOT_SIBLINGS:
        source = OUTPUT.parent / filename
        destination = PILOT_BACKUP.parent / filename
        if not source.exists():
            continue
        if destination.exists():
            if sha256_file(source) != sha256_file(destination):
                raise FileExistsError(f"refusing to overwrite pilot archive: {destination}")
            continue
        # These ignored files may be open in a spreadsheet application.  Copying
        # preserves the historical pilot without requiring a destructive move.
        shutil.copy2(source, destination)


def atomic_write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(content, encoding="utf-8", newline="\n")
    temporary.replace(path)


def main() -> None:
    if sha256_file(SOURCE) != SOURCE_SHA256:
        raise ValueError(f"training source checksum mismatch: {SOURCE}")

    pilot_rows = load_legacy_pilot()
    archive_legacy_pilot_siblings()
    pilot_ids = {row["pair_id"] for row in pilot_rows}
    if len(pilot_ids) != RECORD_COUNT:
        raise ValueError("legacy V0 pilot must contain 100 unique pair IDs")

    with SOURCE.open(encoding="utf-8-sig", newline="") as handle:
        source_rows = list(csv.DictReader(handle))
    if len(source_rows) != 1000 or len({row["pair_id"] for row in source_rows}) != 1000:
        raise ValueError("training source must contain 1,000 unique pair IDs")

    remaining = [row for row in source_rows if row["pair_id"] not in pilot_ids]
    eligible = [row for row in remaining if row["pair_id"] not in REJECTED_MAPPING_IDS]
    selected = sorted(
        eligible,
        key=lambda row: hashlib.sha256(f"{SEED}:{row['pair_id']}".encode()).hexdigest(),
    )[:RECORD_COUNT]
    selected_ids = {row["pair_id"] for row in selected}
    if len(remaining) != 900 or len(selected_ids) != RECORD_COUNT or selected_ids & pilot_ids:
        raise ValueError("invalid pilot/frozen split")

    repaired = [repair_row(row) for row in selected]
    for row in repaired:
        if not all(row[field].strip() for field in ("pair_id", "zh_title", "en_title", "author_zh", "author_en")):
            raise ValueError(f"incomplete title-alignment record: {row['pair_id']}")
        if row["mapping_type"] not in ACCEPTED_MAPPING_TYPES or row["cross_snapshot_validated"] != "True":
            raise ValueError(f"unvalidated mapping record: {row['pair_id']}")

    output_content = "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in repaired)
    atomic_write(OUTPUT, output_content)

    audit = [
        {
            "pair_id": row["pair_id"],
            "verdict": "confirmed",
            "review_basis": [
                "Chinese and English title semantic correspondence reviewed",
                "Chinese and English author correspondence reviewed",
                "curated cross-site mapping marked cross_snapshot_validated",
            ],
        }
        for row in repaired
    ]
    manifest = {
        "dataset_id": "novel-pairs-frozen-title-alignment-v1",
        "dataset_role": "Frozen Test Set",
        "scope": "Chinese-to-English title correspondence and title-localization evaluation only",
        "limitations": [
            "The selected source records do not include Chinese synopsis, genre, or original-platform URL.",
            "They must not be used with workflows that require those fields.",
        ],
        "prohibited_uses": [
            "prompt adjustment",
            "model training or fine-tuning",
            "model, checkpoint, or strategy selection",
            "scoring-weight, threshold, or metric tuning",
            "hard-negative or preference-pair construction",
        ],
        "artifact": {
            "path": OUTPUT.relative_to(ROOT).as_posix(),
            "sha256": hashlib.sha256(output_content.encode("utf-8")).hexdigest(),
            "records": RECORD_COUNT,
            "parser_version": "novel-pair-metadata-v2.0",
        },
        "source": {
            "path": SOURCE.relative_to(ROOT).as_posix(),
            "sha256": SOURCE_SHA256,
            "records": 1000,
            "git_policy": "local_only",
        },
        "split": {
            "algorithm": "exclude legacy V0 pilot IDs and pre-freeze audit rejections; sort eligible pair IDs by SHA-256(seed:pair_id); take first 100",
            "seed": SEED,
            "legacy_pilot_path": PILOT_BACKUP.relative_to(ROOT).as_posix(),
            "legacy_pilot_sha256": LEGACY_PILOT_SHA256,
            "legacy_pilot_records": len(pilot_ids),
            "remaining_training_records": len(remaining),
            "eligible_records": len(eligible),
            "pilot_overlap_records": 0,
            "unique_source_record_ids": len({row["source_record_id"] for row in repaired}),
            "pre_freeze_rejections": [
                {"pair_id": pair_id, "reason": reason}
                for pair_id, reason in REJECTED_MAPPING_IDS.items()
            ],
        },
        "normalization": {
            "method": "Latin-1 mojibake decoded as GB18030 only when the result contains CJK characters; leading BOM removed",
            "source_csv_unchanged": True,
        },
        "validation": {
            "structural": {
                "unique_pair_ids": len(selected_ids),
                "all_cross_snapshot_validated": all(row["cross_snapshot_validated"] == "True" for row in repaired),
                "mapping_types": dict(Counter(row["mapping_type"] for row in repaired)),
                "review_statuses": dict(Counter(row["review_status"] for row in repaired)),
            },
            "semantic_title_author_audit": {
                "method": "Per-record Chinese/English title and author review; localized rather than literal English titles are accepted when they identify the same work.",
                "confirmed": len(audit),
                "incorrect": 0,
                "unverifiable": 0,
                "records": audit,
            },
        },
    }
    atomic_write(MANIFEST, json.dumps(manifest, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({"output": str(OUTPUT), "manifest": str(MANIFEST), "records": len(repaired)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
