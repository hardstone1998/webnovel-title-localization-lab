# Architecture

## Purpose

The architecture supports controlled research, not an online product. Its main
job is to keep data, candidate generation, ranking, and evaluation independently
replaceable and reproducible.

## Logical Flow

```text
Source Dataset
      |
      v
Validation and Provenance
      |
      v
Candidate Generation --------> Candidate Artifact
      |                              |
      v                              v
Hard Constraints              Ranker Comparison
                                     |
                                     v
                              Frozen Evaluation
                                     |
                                     v
                            Metrics and Error Report
```

Candidate artifacts are the central boundary. Generators produce them, rankers
consume them, and evaluators compare rankers over the same candidate pool.

## Layer Responsibilities

| Layer | Owns | Must not own |
| --- | --- | --- |
| Contracts | Record, candidate, label, ranking, and result schemas | Provider SDK logic |
| Data | Ingestion, validation, normalization, splits, fingerprints | Ranking decisions |
| Generation | Named candidate strategies and generation provenance | Final quality judgment |
| Constraints | Factual and structural violation checks | Appeal or style preference |
| Ranking | Rule, LLM, and learned ranking methods | Dataset mutation |
| Evaluation | Metrics, robustness, significance, error aggregation | Training or prompt tuning |
| Orchestration | Stage ordering, configuration resolution, artifact paths | Domain scoring logic |
| Reporting | Tables, summaries, and comparison reports | Hidden metric recomputation |
| Adapters | Model, storage, and annotation-provider integration | Core domain contracts |

## Dependency Direction

Domain contracts sit at the center. Data, generation, constraints, ranking, and
evaluation may depend on those contracts. Provider adapters implement interfaces
defined by the inner layers. Orchestration composes components but should not
contain model-specific or metric-specific logic.

This direction keeps a model provider change from affecting the dataset format
or evaluation rules.

## Planned Package Map

The following map is a target for implementation, not a set of empty packages to
create immediately:

```text
title_localization_lab/
|-- contracts/       # typed domain records and schema versions
|-- data/            # validation, normalization, splits, fingerprints
|-- generation/      # candidate strategies and generation interface
|-- constraints/     # hard checks and violation records
|-- ranking/
|   |-- rules/       # deterministic baseline
|   |-- judges/      # LLM judging protocols
|   `-- learned/     # trainable ranking models
|-- evaluation/      # metrics, robustness, and error analysis
|-- orchestration/   # experiment-stage composition
|-- reporting/       # human-readable research outputs
`-- adapters/        # external model and storage integrations
```

Create a package only when its first behavior and test arrive together. This
avoids a large empty scaffold while preserving a clear destination.

## Core Artifact Contracts

Five artifacts define the research workflow:

| Artifact | Minimum identity |
| --- | --- |
| Source dataset | dataset version, sample IDs, split, content fingerprint |
| Candidate set | candidate-set version, sample and candidate IDs, strategy provenance |
| Label set | rubric version, label source, annotator class, candidate references |
| Ranking result | ranker version, ordered candidate IDs, scores, violations |
| Evaluation result | evaluation version, input fingerprints, metrics, uncertainty |

Artifacts are append-only within a version. Corrections create a new version and
retain the relationship to the superseded artifact.

## Configuration Model

Configuration is layered from stable defaults to a named experiment override.
Resolved configuration is captured with every run. Secrets and provider
credentials come only from the local environment and never appear in config
files or run reports.

## Failure Boundaries

- Invalid source records stop before generation.
- Partial provider failures remain visible and are never treated as empty titles.
- Constraint violations remain attached to candidates even if a ranker ignores
  them.
- Metric failures invalidate the evaluation artifact rather than producing a
  partial headline score.
- Reports read completed artifacts and do not trigger generation or training.

## Architecture Gates

Before V0 implementation begins:

- source and candidate schema responsibilities are agreed
- frozen-set policy and rubric versioning are documented
- one experiment manifest shape is selected
- hard constraints are separated from preference dimensions

Before a learned ranker begins:

- V0 and V1 artifacts are reproducible
- candidate pools are versioned and fixed for comparison
- evaluation reliability and human disagreement are measured
- leakage checks are part of dataset preparation

## Non-Goals

The initial architecture does not include a web API, user accounts, online
feedback ingestion, model serving, distributed jobs, a feature store, or a
general workflow platform. Those concerns should be introduced only when a
research result requires them.
