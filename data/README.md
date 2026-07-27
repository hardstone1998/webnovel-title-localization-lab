# Data

This directory exposes public data contracts and safe examples. It is not the
storage location for distributable copies of scraped platform content.

Tracked in Git:

- `schemas/`: versioned data contracts
- `examples/`: synthetic, redistributable records used to explain contracts

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
