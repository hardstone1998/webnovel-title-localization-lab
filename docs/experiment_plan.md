# Experiment Plan

## Research Sequence

The project advances only when the current stage produces a reproducible
artifact and an interpretable result. A more complex ranker is not justified
until simpler baselines and evaluation reliability are established.

## Common Controls

All ranking comparisons use the same candidate-set version, split manifest,
rubric version, metric implementation, and Frozen Test Set. Experiment
reports must disclose seeds, model and prompt versions, excluded records, cost,
latency, and failed requests.

Prompt changes, candidate-generation changes, ranking changes, and training-data
changes are evaluated separately before they are combined. Training and
development failures may enter the preference-data flywheel; Frozen Test Set
failures are report-only.

## V0: Prompt-Diverse Generation and Pointwise Baseline

Question: can strategy-diverse prompting plus eight-dimension pointwise scoring
establish a reproducible baseline?

Planned comparison:

- direct translation prompt
- strategy-diverse candidate prompt
- unranked generation order
- pointwise dimension scores with deterministic weighted recomputation

Exit criteria:

- repeatable candidate artifact with stable IDs
- pointwise rubric, weights, and validity constraints documented
- Top 1 and Top 3 results on pilot / development data
- failure analysis using the shared taxonomy
- no use of the Frozen Test Set for tuning

The existing `reports/baseline_v0.md` is pilot / early-development evidence. Its
100 observed records are not the separately reserved Frozen Test Set.

## V1: Candidate Generation Optimization

Question: can generation-strategy changes improve faithful candidate coverage,
platform-anchor coverage, and useful diversity?

Planned comparison:

- V0 generation strategies
- revised strategy-specialized prompts
- ablations by source-title, synopsis, and market-localized strategy
- the fixed V0 pointwise ranker over every candidate pool

Exit criteria:

- complete candidate artifacts with strategy provenance
- candidate validity, uniqueness, diversity, and coverage report
- generation-only comparison with ranking logic held fixed
- documented choice of the V2 candidate pool

## V2: Pairwise and Listwise Preference Ranking

Question: are pairwise or listwise preferences more stable and useful than the
V0 pointwise weighted score?

Planned comparison:

- V0 pointwise scoring
- pairwise preference judging
- listwise ranking
- repeated judging with candidate-order permutations
- comparison with and without published-title anchors

Exit criteria:

- one fixed candidate pool for every ranking protocol
- position-bias, repeatability, cost, and latency report
- agreement analysis against available preference labels
- chosen preference protocol and documented rejected alternatives

## V3: Reward Model

Question: does a task-specific Reward Model trained on weak preferences and hard
negatives outperform the pointwise and LLM-judge baselines?

Planned comparison:

- pointwise V0 baseline
- selected V2 LLM preference judge
- Reward Model trained on Platform Anchors and mined hard negatives
- ablations by weak-label source, negative-mining strategy, and feature family

Exit criteria:

- versioned training, development, and evaluation manifests
- checkpoint and threshold selection using development data only
- uncertainty intervals, subgroup results, and error-type analysis
- improvement without an increase in critical violations
- explicit practical-significance, cost, and latency assessment

## V4: Reward Model with Human Feedback

Question: where does a limited amount of independent human preference data
correct weak-label bias?

Planned comparison:

- weak labels only
- human labels only at matched sample size
- weak labels plus human labels
- label-source and genre ablations

Exit criteria:

- annotation protocol and reviewer agreement report
- learning curve by human-label volume
- analysis of corrected and newly introduced errors
- final limitations and deployment non-claims

## Frozen Test Comparison

V0 through V4 release candidates may be compared on the same 100-record Frozen
Test Set only after each candidate and its metrics are predeclared. Test-set
outcomes are used for final reporting, not for prompt revision, hard-negative
construction, Reward Model training, checkpoint selection, or threshold tuning.

## Required Experiment Artifacts

Each experiment needs a manifest, immutable input fingerprints, resolved
configuration, environment summary, metrics file, human-readable report, and
references to candidate and label artifacts. Naming and storage rules live in
[../experiments/README.md](../experiments/README.md).

## Decision Rule

Promote a method only when it improves the declared primary metric without
increasing critical violations, survives order-robustness checks, and has a
cost/latency profile appropriate for the research goal.
