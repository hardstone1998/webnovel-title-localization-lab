# Experiment Plan

## Research Sequence

The project advances only when the current stage produces a reproducible
artifact and an interpretable result. A more complex ranker is not justified
until simpler baselines and evaluation reliability are established.

## Common Controls

All ranking comparisons use the same candidate-set version, split manifest,
rubric version, metric implementation, and frozen evaluation set. Experiment
reports must disclose seeds, model and prompt versions, excluded records, cost,
latency, and failed requests.

## V0: Rule and Prompt Baseline

Question: can explicit title-quality rules create a meaningful lower bound?

Planned comparison:

- direct translation prompt
- strategy-diverse candidate prompt
- unranked generation order
- deterministic weighted-rule ranker

Exit criteria:

- repeatable candidate artifact with stable IDs
- rule weights and hard constraints documented
- Top 3 result on a development set
- failure analysis using the shared taxonomy
- no use of the frozen evaluation set for tuning

## V1: LLM Judge Baseline

Question: which judging protocol is useful and stable enough to be a baseline?

Planned comparison:

- pointwise scoring
- pairwise preference
- listwise ranking
- repeated judging with candidate-order permutations

Exit criteria:

- position-bias and repeatability report
- agreement analysis against independent human preferences
- cost and latency comparison
- chosen protocol and rejected alternatives documented

## V2: Learned Ranker

Question: does a task-specific learned ranker outperform both baselines?

Planned comparison:

- rule baseline
- selected LLM judge
- learned ranker trained on weak labels
- ablations by label source and feature family

Exit criteria:

- versioned training and evaluation manifests
- uncertainty or confidence intervals for primary metrics
- untouched frozen-set result
- subgroup and error-type analysis
- explicit result for practical significance, not only statistical significance

## V3: Human Feedback Enhancement

Question: where does a small amount of human preference data correct weak-label
bias?

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

## Required Experiment Artifacts

Each experiment needs a manifest, immutable input fingerprints, resolved
configuration, environment summary, metrics file, human-readable report, and
references to candidate and label artifacts. Naming and storage rules live in
[../experiments/README.md](../experiments/README.md).

## Decision Rule

Promote a method only when it improves the declared primary metric without
increasing critical violations, survives order-robustness checks, and has a
cost/latency profile appropriate for the research goal.
