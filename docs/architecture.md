# Architecture

## Purpose

The architecture supports controlled research and a synchronous protected Web
API. Its main job is to keep data, candidate generation, ranking, and evaluation
independently replaceable and reproducible.

The decision architecture separates **Faithfulness / Validity** from
**Platform Preference**. Validity checks enforce basic content constraints;
preference ranking operates only among candidates that remain eligible. A high
platform-fit or appeal score must never cancel a material factual violation.

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
Validity Filtering            Platform Preference Ranking
       |                              |
       +------------------------------+
                                      |
                                      v
                                     Top-K
                                      |
                    +-----------------+-----------------+
                    |                                   |
                    v                                   v
          Development Evaluation              Frozen Test Evaluation
                    |                                   |
                    v                                   v
             Failure Mining                    Final Report Only
                    |
                    v
      Hard Negatives and Preference Data
                    |
                    v
             Reward Model Update
```

Candidate artifacts are the central boundary. Generators produce them, rankers
consume them, and evaluators compare rankers over the same candidate pool.

The Frozen Test branch is deliberately terminal: its samples, labels, and
failures do not enter prompt revision, model training, hard-negative mining,
model selection, or threshold tuning.

## Data Flywheel

The project models a repeatable localization feedback loop rather than a single
training run:

```text
historical platform data
  -> candidate generation
  -> automated evaluation and weak-supervision ranking
  -> development-set failure-case mining
  -> hard-negative construction
  -> preference-dataset updates
  -> Reward Model updates
  -> new inference version
  -> new development failures
```

The accumulated assets are the versioned candidates, failure cases, preference
pairs, labels, and evaluation artifacts. Frozen-test failures are excluded from
the loop so that the final comparison remains an estimate of generalization.

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

## Package Map

The implemented package map follows the service organization used by the
reference API while keeping the research pipeline isolated from HTTP concerns:

```text
app/
|-- api/             # routes, safe HTTP errors, health checks
|-- config/          # environment settings and pipeline config parsing
|-- domain/          # typed contracts, API models, domain errors
|-- llm/             # deterministic and OpenAI-compatible adapters
|-- pipeline/        # generation, scoring, reporting, orchestration
|-- utils/           # artifacts, logging, input conversion
`-- validators/      # contract and hard-constraint validation
```

Each package owns behavior with corresponding tests; HTTP routes do not embed
provider or ranking decisions.

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

Before V0 is declared reproducible:

- source and candidate schema responsibilities are agreed
- frozen-set policy and rubric versioning are documented
- one experiment manifest shape is selected
- hard constraints are separated from preference dimensions

Before V3 Reward Model training begins:

- V0, V1, and V2 artifacts are reproducible
- candidate pools are versioned and fixed for comparison
- the chosen preference protocol has a reliability report
- leakage checks are part of dataset preparation

## Non-Goals

The initial architecture does not include user accounts, online feedback
ingestion, distributed jobs, a feature store, or a general workflow platform.
The synchronous API does not persist requests or results, and it has no queue
worker, database, or authentication layer.
