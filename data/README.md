# Data

This directory exposes public data contracts and safe examples. It is not the
storage location for distributable copies of scraped platform content.

Tracked in Git:

- `schemas/`: versioned data contracts
- `examples/`: synthetic, redistributable records used to explain contracts
- `manifests/`: non-sensitive dataset inventories, fingerprints, and integrity notes
- `batch_tests/`: version-controlled request inputs and deterministic batch-validation outputs
- `processed/novel_pairs/100/novel_pairs_100.jsonl`: the explicitly versioned,
  100-record Frozen Title-Alignment Test Set; it is an exception to the local
  processed-data default and must not be used for tuning or training.

Local by default and ignored by Git:

- `raw/`: original acquired records
- `external/`: third-party datasets preserved in their source form
- `interim/`: normalized or partially validated data
- `processed/`: experiment-ready datasets
- `private/`: human annotations or restricted content
- `frozen/`: protected milestone evaluation sets

Each local dataset should have a non-sensitive manifest containing its version,
source classes, schema version, record counts, split fingerprint, content hash,
and redistribution decision. The governing policy is
[../docs/data_card.md](../docs/data_card.md).

The current local novel-pair inventory is documented in
[`manifests/novel_pairs_2026-07-29.json`](manifests/novel_pairs_2026-07-29.json).
The frozen-set split and per-record audit are documented without title text in
[`manifests/frozen_title_alignment_v1.json`](manifests/frozen_title_alignment_v1.json).
