# WebNovel Title Localization Lab

A lightweight research project for Chinese web-novel title localization. The goal is to explore how to generate and rank English title candidates for overseas web-novel platforms such as WebNovel.

This project is intentionally scoped as a small, reproducible portfolio project rather than a production translation platform.

## Project Goal

Given a Chinese web-novel title, synopsis, genre, and story hook, the system generates several English title candidates and ranks them by:

- faithfulness to the story premise
- English naturalness
- platform-style fit
- reader appeal
- risk of misleading or over-hyped titles

The core research question is:

> Can a task-specific ranking model, trained with weak platform labels and a small amount of human preference data, rank title candidates more reliably than rule-based scoring or general LLM judging?

## Initial Scope

V1 focuses on a narrow scenario:

- Source language: Chinese
- Target language: English
- Domain: web-novel titles
- Target style: WebNovel-like overseas platform naming
- Input: source title, synopsis, genre, protagonist, core conflict, story hook
- Output: 6-8 English title candidates with ranked recommendations

Out of scope for V1:

- full novel translation
- running a reading website
- real CTR optimization
- large-scale crawling of novel body text
- PPO/RL training
- 16-language localization

## Planned Pipeline

```text
source title + synopsis + genre
-> candidate generation
-> hard constraint filtering
-> rule-based baseline
-> LLM judge baseline
-> reward/ranking model
-> human preference evaluation
-> error analysis report
```

## Data Strategy

The project separates data into three layers:

1. Weak supervision data
   - platform-published translated titles as anchor candidates
   - model-generated candidates
   - synthetic pairwise/listwise preference labels

2. Developer-labeled data
   - small manually reviewed set for rubric design and error analysis

3. Independent human evaluation set
   - small frozen test set judged by external readers or English-capable reviewers

Raw platform content should stay local by default. The public repository should prefer scripts, schemas, IDs, synthetic examples, aggregated metrics, and documentation rather than redistributing large amounts of platform text.

## Evaluation

Main metrics planned for V1:

- Pairwise Accuracy
- Hit@3
- NDCG@K
- position robustness
- constraint violation rate
- error type distribution
- inference cost and latency

## Repository Layout

```text
webnovel-title-localization-lab/
├── README.md
├── pyproject.toml
├── .gitignore
├── configs/
├── data/
│   ├── examples/
│   └── schemas/
├── docs/
│   ├── data_card.md
│   ├── error_taxonomy.md
│   └── experiment_plan.md
├── experiments/
├── src/
│   └── title_localization_lab/
└── tests/
```

## Version Roadmap

### V0: Rule and Prompt Baseline

- Define title quality rubric
- Generate candidates by strategy
- Score candidates with weighted dimensions
- Produce a simple Top 3 ranking

### V1: LLM Judge Baseline

- Compare absolute scoring, listwise ranking, and pairwise ranking
- Test prompt and candidate order robustness
- Analyze judge bias toward long or over-dramatic titles

### V2: Reward Model

- Train a small ranking model using weak labels and generated candidates
- Compare against rule baseline and LLM judge baseline
- Evaluate on a frozen human-labeled test set

### V3: Human Feedback Enhancement

- Add a small amount of independent human preference data
- Measure whether human labels correct weak-supervision bias
- Produce error analysis and ablation report

## Current Status

Project initialized. No data collection, model training, or service code has been implemented yet.
