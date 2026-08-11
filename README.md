# WebNovel Title Localization Lab

A reproducible research lab and synchronous Web API for generating and ranking
English titles for Chinese web novels. It is evaluation-first and deployable as
a small protected service, not a reader-facing translation platform.

## Research Positioning

- The project learns and reproduces the English title preferences observed on
  WebNovel and similar overseas web-novel platforms.
- Platform-published titles are treated as **Platform Anchors / Weak Labels**,
  not absolute ground truth or uniquely optimal translations.
- The evaluation protocol reserves a separate 100-record **Frozen Test Set**
  that is excluded from prompt and rule design, model training, model and
  checkpoint selection, scoring-weight changes, and threshold tuning.
- The long-term research loop is **candidate generation -> evaluation ->
  failure mining -> preference data -> Reward Model updates**. Failures from the
  Frozen Test Set are report-only and never enter this feedback loop.

## Research Question

Can platform history, weak preference data, hard negatives, and a small amount
of human feedback support a reproducible system that generates faithful titles
and ranks them according to the target platform's established naming patterns?

Title quality is treated as a multi-objective decision:

- faithfulness to the premise
- natural English
- genre and platform fit
- reader appeal
- low risk of clickbait, spoilers, or invented facts

## Decision Framework

The task is split into two related but independently inspectable objectives:

1. **Faithfulness / Validity** acts as a hard constraint or risk filter. It
   checks semantic drift, character and relationship errors, unsupported genre
   or ability claims, spoilers, excessive clickbait, and titles so generic that
   they lose the work's central hook.
2. **Platform Preference** ranks candidates that pass the validity checks by how
   closely they match the target platform's observed English naming patterns.

The resulting decision path is:

```text
Candidate Generation -> Validity Filtering -> Platform Preference Ranking -> Top-K
```

This separation prevents a high style or appeal score from hiding a material
content error.

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

The project does not claim to improve real CTR or paid conversion, to always
outperform platform editors, or to represent the preferences of all English
readers. It tests what can be reproduced offline when real online commercial
feedback is unavailable.

## System Flow

```text
source record
  -> validation and provenance checks
  -> candidate generation by named strategies
  -> validity filtering
  -> platform-preference ranking
  -> Top-K and versioned evaluation
  -> development-set failure mining
  -> hard negatives and preference data
  -> Reward Model update and a new version
```

Every stage exchanges versioned artifacts rather than hidden in-memory state.
This makes it possible to compare rankers against the exact same candidates and
to reproduce a result without regenerating upstream data.

Frozen-test evaluation branches from a declared release candidate and ends in a
report. Its samples and failure cases do not flow back into prompts, rules,
training data, weights, thresholds, or model selection.

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
| V0 | Can strategy-diverse prompting plus pointwise weighted scoring establish a useful baseline? | Reproducible candidate and score artifacts with documented pilot failures |
| V1 | Does a better candidate-generation strategy improve coverage and diversity? | Improvement with the V0 ranker held fixed |
| V2 | Are pairwise or listwise preferences more reliable than pointwise scores? | Blind, order-robust comparison over a fixed candidate pool |
| V3 | Does a Reward Model trained on weak preferences and hard negatives outperform the baselines? | Predeclared improvement without more critical violations |
| V4 | Where does limited independent human feedback correct weak-label bias? | Ablation of weak labels, human labels, and their combination |

See [docs/experiment_plan.md](docs/experiment_plan.md) for stage gates and
[docs/evaluation_protocol.md](docs/evaluation_protocol.md) for the common
evaluation contract.

## Documentation Map

- [Architecture](docs/architecture.md): boundaries, dependency direction, and
  the planned package map
- [Data card](docs/data_card.md): provenance, release policy, splits, and leakage
  controls, including Platform Anchor semantics
- [Evaluation protocol](docs/evaluation_protocol.md): frozen-set and human
  evaluation rules and published-title diagnostics
- [Error taxonomy](docs/error_taxonomy.md): annotation categories and severity
- [Experiment plan](docs/experiment_plan.md): research sequence and promotion
  criteria
- [Two-stage title selection](docs/two_stage_title_selection.md): Chinese usage
  guide for 12-candidate generation, eight-dimension scoring, CLI operation,
  artifacts, and provider setup

## OpenAI-compatible Provider Quick Start

The deterministic adapter remains the offline default. To use a model provider,
set `LLM_MODEL`, `LLM_BASE_URL`, `LLM_TIMEOUT_SECONDS`, `LLM_MAX_TOKENS`, and `LLM_API_KEY` in
`.env`:

```powershell
title-localization `
  --input data/examples/sample_title_case.json `
  --config configs/title_selection.default.json `
  --output-dir artifacts/provider-example-run `
  --adapter openai-compatible
```

Do not put the key in JSON configuration, source files, artifacts, or committed
scripts. The provider fields are resolved from `.env`; explicit process
environment variables take precedence.

## FastAPI Service

Copy the environment template and configure the provider credential before
starting the synchronous API locally:

```powershell
Copy-Item .env.example .env
uv run uvicorn app.main:app --host 127.0.0.1 --port 8000
```

The service exposes `GET /`, `GET /healthz`, `GET /health`, `GET /readyz`,
interactive OpenAPI documentation at `/docs`, and `POST /v1/title-localizations`.
Every response includes `X-Request-ID`; pass that header to correlate logs. It
always uses the server-side OpenAI-compatible adapter configured through
`LLM_*` environment variables. The API never returns deterministic synthetic
titles or scores: a missing credential or unavailable provider returns a
structured `502` error with no partial result. `GET /readyz` reports ready only
when its configured provider has local configuration and a credential
available. The first release is synchronous and is intended
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
  debug = $true # Optional: return per-candidate scores.
} | ConvertTo-Json -Depth 4

Invoke-RestMethod `
  -Method Post `
  -Uri http://127.0.0.1:8000/v1/title-localizations `
  -ContentType "application/json" `
  -Body $body
```

On success, the API returns the selected title and detailed scores for every
candidate in final rank order:

```json
{
  "selected": {
    "candidate_id": "cand_...",
    "title": "Every Check-In Makes Me Stronger",
    "score": 87.5
  },
  "ranked_titles": [
    {
      "rank": 1,
      "candidate_id": "cand_...",
      "title": "Every Check-In Makes Me Stronger",
      "dimensions": {"semantic_fidelity": 9, "natural_english": 8},
      "total_score": 87.5
    }
  ]
}
```

It does not return `candidate_set`, `ranking_result`, or `report`. Model calls
emit request-correlated INFO logs; these include stage summaries but never API
keys, authorization headers, raw prompts, source synopses, or score rationales.

The optional request field `debug` remains supported and returns the same
per-candidate data under a `debug` field for callers using the earlier debug
contract.

## Current Status

The repository now includes an executable two-stage baseline and a deployable
FastAPI wrapper: three generation
strategies produce 12 English title candidates, then an eight-dimension model
judge is verified with deterministic weighted arithmetic to select one eligible
winner. The default deterministic adapter, schemas, CLI, synthetic example, and
offline tests are implemented. The separately held-out 100-record Frozen Test
Set has not yet been materialized. Learned ranking, private-data ingestion, and
asynchronous/online services remain future work.
