# Data Card

## Status

This is the governing data contract for the project. Dataset statistics are
intentionally left blank until collection begins. Each released dataset version
must update this document and link to its manifest.

## Intended Use

The dataset supports offline research on Chinese-to-English web-novel title
generation and preference ranking. It is not intended to represent reader
behavior, estimate commercial CTR, or provide a general translation benchmark.

## Record Families

| Family | Purpose | Git policy |
| --- | --- | --- |
| Source records | Title, synopsis, genre, and story context | Local unless redistribution is verified |
| Candidate sets | Generated title options with strategy provenance | Publish only for redistributable sources |
| Weak labels | Platform anchors or synthetic preferences | Publish only with provenance and caveats |
| Developer labels | Rubric calibration and error analysis | Publish aggregate results by default |
| Human evaluation | Blind preference judgments | Keep raw annotations private by default |
| Synthetic examples | Schema and workflow demonstrations | Track in Git |

## Required Provenance

Every source record should have a stable sample ID, source class, acquisition
date or dataset version, language pair, redistribution status, and content hash.
Every candidate should additionally record its candidate ID, generation strategy,
generator version, prompt or configuration version, and parent sample ID.

Labels should identify the annotation protocol, rubric version, annotator class,
timestamp, and whether the label is weak, developer-provided, or independent
human evaluation.

## Data Lifecycle

```text
raw or external
  -> provenance and license review
  -> normalization
  -> schema validation
  -> deduplication and leakage grouping
  -> development or frozen split
  -> candidate and label artifacts
  -> aggregate release
```

Raw, external, interim, processed, private, and frozen data directories are local
by default. Only schemas, synthetic examples, manifests without sensitive text,
and aggregate results belong in the public repository.

## Split Policy

- Split before candidate generation or model tuning.
- Group records from the same novel, alternate title, franchise, or near-duplicate
  synopsis into one split.
- Keep the frozen evaluation set inaccessible to prompt and weight tuning.
- Record the split algorithm, seed, grouping key, and dataset fingerprint.
- Create a new frozen-set version rather than silently replacing records.

## Leakage Controls

Check for exact and near-duplicate source titles, translated aliases, repeated
synopses, series relationships, and candidate overlap across splits. Platform
published titles may be used as weak signals but must not appear as hidden labels
inside generation prompts for evaluation records.

## Quality Checks

- required-field and schema validation
- language and empty-text checks
- duplicate and near-duplicate detection
- genre vocabulary normalization
- provenance and redistribution review
- candidate count and uniqueness checks
- annotation consistency and agreement summaries

## Privacy, Licensing, and Release

Do not collect reader identities or other personal data. Store source URLs and
platform IDs only when they are necessary for provenance. A public release must
contain only material with a clear redistribution basis or transformed aggregate
statistics that do not reconstruct source text.

## Known Limitations

Expected limitations include platform-specific style bias, weak-label noise,
genre imbalance, subjective appeal judgments, English reviewer demographics,
model-generated candidate artifacts, and limited evidence about real reader
behavior.

## Version Checklist

A dataset version is ready only when its schema version, source inventory,
license decision, split fingerprint, duplicate report, basic statistics, and
known limitations are documented.
