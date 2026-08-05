# WebNovel Title Localization Lab

A reproducible research lab and synchronous Web API for generating and ranking
English titles for Chinese web novels. It is evaluation-first and deployable as
a small protected service, not a reader-facing translation platform.

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
- offline evaluation and a synchronous HTTP API

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
|-- app/           # FastAPI entry point and application layers
|   |-- api/       # HTTP routes and error responses
|   |-- config/    # environment and reviewed profile loading
|   |-- domain/    # API models, contracts, and errors
|   |-- llm/       # deterministic and provider adapters
|   |-- pipeline/  # generation, ranking, and orchestration
|   |-- utils/     # artifact, logging, and conversion helpers
|   `-- validators/# pipeline contract validation
|-- configs/       # reviewed experiment configuration
|-- data/
|   |-- examples/  # redistributable synthetic records
|   `-- schemas/   # versioned public data contracts
|-- docs/          # architecture, data, evaluation, and research decisions
|-- experiments/   # experiment manifests and short result reports
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

## FastAPI Service

Copy the environment template and configure at least one reviewed provider
credential before starting the synchronous API locally:

```powershell
Copy-Item .env.example .env
uv run uvicorn app.main:app --host 127.0.0.1 --port 8000
```

The service exposes `GET /`, `GET /healthz`, `GET /health`, `GET /readyz`,
interactive OpenAPI documentation at `/docs`, and `POST /v1/title-localizations`.
Every response includes `X-Request-ID`; pass that header to correlate logs. It accepts only the reviewed
`default` and `deepseek` configuration profiles and always uses the server-side
`openai-compatible` adapter. The API never returns deterministic synthetic
titles or scores: a missing credential or unavailable provider returns a
structured `502` error with no partial result. `GET /readyz` reports ready only
when at least one reviewed provider profile has local configuration and a
credential available. The first release is synchronous and is intended
for trusted local or protected deployments; it does not include authentication,
rate limiting, batch jobs, or persisted API results.

Run the containerized service after creating `.env`:

```powershell
docker compose up --build
```

The API listens on port `8000` by default; set `HOST_PORT` in `.env` to change
the host-side port. The image runs a single API process and has no Redis, worker,
database, or persistent result volume.

Example model-backed request:

```powershell
$body = @{
  source = @{
    sample_id = "api_example_001"
    source_title = "开局觉醒神级签到系统"
    source_language = "zh"
    target_language = "en"
    genre = "system_fantasy"
    genre_zh = "系统玄幻"
    synopsis = "A cultivator gains a check-in system after being expelled from his sect."
  }
  config_profile = "default"
} | ConvertTo-Json -Depth 4

Invoke-RestMethod `
  -Method Post `
  -Uri http://127.0.0.1:8000/v1/title-localizations `
  -ContentType "application/json" `
  -Body $body
```

On success, the API returns only the selected title and authoritative score,
plus the remaining titles in final rank order:

```json
{
  "selected": {
    "candidate_id": "cand_...",
    "title": "Every Check-In Makes Me Stronger",
    "score": 87.5
  },
  "unselected_titles": ["...", "..."]
}
```

It does not return `candidate_set`, `ranking_result`, or `report`. Model calls
emit request-correlated INFO logs; these include stage summaries but never API
keys, authorization headers, raw prompts, source synopses, or score rationales.

## Current Status

The repository now includes an executable two-stage baseline and a deployable
FastAPI wrapper: three generation
strategies produce 12 English title candidates, then an eight-dimension model
judge is verified with deterministic weighted arithmetic to select one eligible
winner. The default deterministic adapter, schemas, CLI, synthetic example, and
offline tests are implemented. Learned ranking, private-data ingestion, and
asynchronous/online services remain future work.
