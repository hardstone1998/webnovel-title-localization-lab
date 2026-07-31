# WebNovel Title Localization Lab

A small, reproducible research lab for generating and ranking English titles for
Chinese web novels. It is designed as an evaluation-first portfolio project, not
as a production translation platform.

## Research Question

Can a task-specific ranker, trained with weak platform signals and a small amount
of human preference data, rank title candidates more reliably than a rule-based
baseline or a general-purpose LLM judge?

Title quality is treated as a multi-objective decision:

- faithfulness to the premise
- natural English
- genre and platform fit
- reader appeal
- low risk of clickbait, spoilers, or invented facts

## Scope

The first complete research cycle is intentionally narrow:

- Chinese source and English target
- web-novel title localization
- title, synopsis, genre, protagonist, conflict, and hook as input context
- six to eight candidates and a ranked Top 3 as output
- offline evaluation only

Full-text translation, a reader-facing product, live CTR optimization, broad web
crawling, reinforcement learning, and multilingual expansion are outside the
initial scope.

## System Flow

```text
source record
  -> validation and provenance checks
  -> candidate generation by named strategies
  -> hard-constraint filtering
  -> rule, LLM, or learned ranking
  -> frozen-set evaluation
  -> error analysis and experiment report
```

Every stage exchanges versioned artifacts rather than hidden in-memory state.
This makes it possible to compare rankers against the exact same candidates and
to reproduce a result without regenerating upstream data.

## Architecture Principles

- Evaluation first: define the frozen set and rubric before tuning a ranker.
- Separate generation from ranking: a ranking experiment must not silently
  change its candidate pool.
- Separate hard constraints from preferences: factual violations are filtered
  or flagged before style and appeal are scored.
- Track provenance: each record, candidate, label, and result needs a stable ID.
- Keep private data local: publish schemas, synthetic examples, aggregate
  metrics, and reproducible procedures.
- Prefer configuration over experiment-specific branches or copied scripts.

The detailed boundaries and future package map are documented in
[docs/architecture.md](docs/architecture.md).

## Repository Layout

```text
webnovel-title-localization-lab/
|-- configs/       # reviewed experiment configuration
|-- data/
|   |-- examples/  # redistributable synthetic records
|   `-- schemas/   # versioned public data contracts
|-- docs/          # architecture, data, evaluation, and research decisions
|-- experiments/   # experiment manifests and short result reports
|-- src/
|   `-- title_localization_lab/
`-- tests/         # contract, unit, integration, and regression checks
```

Local raw data, processed corpora, model files, run outputs, private labels, and
tool workspaces are excluded from Git.

## Milestones

| Stage | Question | Exit condition |
| --- | --- | --- |
| V0 | Can deterministic rules establish a useful floor? | Reproducible Top 3 baseline and documented failures |
| V1 | Which LLM judging protocol is stable enough? | Blind comparison of pointwise, pairwise, and listwise judging |
| V2 | Does a learned ranker beat both baselines? | Improvement on the untouched frozen set with uncertainty reported |
| V3 | Does limited human feedback correct weak-label bias? | Ablation showing where human labels help and where they do not |

See [docs/experiment_plan.md](docs/experiment_plan.md) for stage gates and
[docs/evaluation_protocol.md](docs/evaluation_protocol.md) for the common
evaluation contract.

## Documentation Map

- [Architecture](docs/architecture.md): boundaries, dependency direction, and
  the planned package map
- [Data card](docs/data_card.md): provenance, release policy, splits, and leakage
  controls
- [Evaluation protocol](docs/evaluation_protocol.md): frozen-set and human
  evaluation rules
- [Error taxonomy](docs/error_taxonomy.md): annotation categories and severity
- [Experiment plan](docs/experiment_plan.md): research sequence and promotion
  criteria
- [Two-stage title selection](docs/two_stage_title_selection.md): Chinese usage
  guide for 12-candidate generation, eight-dimension scoring, CLI operation,
  artifacts, and provider setup

## DeepSeek Quick Start

The deterministic adapter remains the offline default. To opt into DeepSeek,
keep the credential in the current PowerShell environment and select the
reviewed provider preset explicitly:

```powershell
$env:DEEPSEEK_API_KEY = "<your-deepseek-api-key>"
title-localization `
  --input data/examples/sample_title_case.json `
  --config configs/title_selection.deepseek.json `
  --output-dir artifacts/deepseek-example-run `
  --adapter openai-compatible
```

Do not put the key in configuration, source files, artifacts, or committed
scripts. See the
[DeepSeek setup guide](docs/two_stage_title_selection.md#使用-deepseek-api-key)
for model selection, cleanup, and error behavior.

## Current Status

The repository now includes an executable two-stage baseline: three generation
strategies produce 12 English title candidates, then an eight-dimension model
judge is verified with deterministic weighted arithmetic to select one eligible
winner. The default deterministic adapter, schemas, CLI, synthetic example, and
offline tests are implemented. Learned ranking, private-data ingestion, and
online services remain future work.
