# Data Card

## Status

This is the governing data contract for the project. Private pilot data exists,
but public dataset statistics remain intentionally blank until a releasable
dataset version is declared. Each released dataset version must update this
document and link to its manifest.

## Intended Use

The dataset supports offline research on Chinese-to-English web-novel title
generation and preference ranking. It is not intended to represent reader
behavior, estimate commercial CTR, or provide a general translation benchmark.

The target task is to learn and reproduce title preferences observed on
WebNovel and similar overseas web-novel platforms while preserving basic story
faithfulness. It does not assume that a platform-published title is the uniquely
best translation or the title that all English readers would prefer.

## Record Families

| Family | Purpose | Git policy |
| --- | --- | --- |
| Source records | Title, synopsis, genre, and story context | Local unless redistribution is verified |
| Candidate sets | Generated title options with strategy provenance | Publish only for redistributable sources |
| Weak labels | Published-title Platform Anchors or synthetic preferences | Publish only with provenance and caveats |
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

Dataset roles are separated before prompt tuning, candidate generation for
training, or model development:

| Role | Intended use | May influence system decisions? |
| --- | --- | --- |
| Pilot / early development | Task validation, prompt baseline, rubric design, error-taxonomy discovery | Yes; findings are exploratory |
| Training | Candidate generation, weak preference pairs, hard-negative mining, Reward Model training, and later SFT or preference optimization | Yes; training only |
| Development | Prompt, rule, judge, weight, threshold, model, and checkpoint selection; error analysis and ablations | Yes; development only |
| Frozen Test Set | Final evaluation of predeclared release candidates | No |

The project reserves a separate 100-record Frozen Test Set. The 100-record V0
baseline batch already analyzed in `reports/baseline_v0.md` is pilot / early
development evidence and must not be relabeled as frozen test data. The frozen
set must be sampled separately from records that have not influenced prompts,
rules, labels, model selection, or implementation decisions.

- Split before candidate generation or model tuning.
- Group records from the same novel, alternate title, franchise, or near-duplicate
  synopsis into one split.
- Keep the Frozen Test Set inaccessible to prompt and rule design, model
  training, model and checkpoint selection, scoring-weight changes, threshold
  tuning, and hard-negative mining.
- Record the split algorithm, seed, grouping key, and dataset fingerprint.
- Create a new frozen-set version rather than silently replacing records.

## Weak Supervision Semantics

A platform-published English title is recorded as **Published Title / Platform
Anchor / Weak Positive**. It demonstrates a naming choice that the platform
actually adopted, but may also reflect editorial policy, historical convention,
SEO, commercial constraints, or individual judgment.

Platform Anchors therefore support preference learning and agreement metrics;
they are not absolute ground truth, uniquely correct translations, or direct
evidence of CTR. Any preference pair derived from an anchor must retain its weak
label source and construction method.

## Leakage Controls

Check for exact and near-duplicate source titles, translated aliases, repeated
synopses, series relationships, and candidate overlap across splits. Platform
published titles may be used as weak signals but must not appear as hidden labels
inside generation prompts for evaluation records.

Frozen-test examples, published titles, failures, and hard negatives must not be
copied into training or development artifacts. Observing a frozen-test failure
does not authorize a prompt, rule, weight, threshold, or checkpoint change.

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
