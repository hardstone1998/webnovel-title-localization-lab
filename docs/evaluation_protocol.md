# Evaluation Protocol

## Purpose

This protocol ensures that improvements reflect better ranking rather than a
changed candidate pool, leaked labels, or unstable judge behavior.

## Evaluation Sets

Use four data roles with non-overlapping decision authority:

| Set | Purpose | Tuning allowed |
| --- | --- | --- |
| Pilot / early development | Validate the task, establish the baseline, design the rubric and taxonomy | Yes; exploratory only |
| Training | Fit learned models and construct weak preferences or hard negatives | Training only |
| Development | Prompts, rules, judges, weights, thresholds, model and checkpoint selection, diagnostics, and ablations | Yes |
| Frozen Test Set | Final comparison of predeclared release candidates and reporting | No |

The protocol requires a Frozen Test Set of 100 separately held-out records. Once
created, it is versioned, fingerprinted, grouped to prevent related-title
leakage, and opened only for scheduled evaluation of a release candidate whose
prompts, rules, model, checkpoint, weights, thresholds, and metrics have already
been fixed.

The 100 records already used in the V0 baseline are not this Frozen Test Set;
they are pilot / early-development data because their examples and outcomes have
already been observed.

## Frozen Test Set Rules

Frozen-test records and outcomes must not be used to:

- modify prompts, rubrics, scoring rules, or error-handling logic;
- train or fine-tune a Reward Model or another model;
- select a model, checkpoint, judge protocol, or generation strategy;
- adjust dimension weights, thresholds, tie-break rules, or metrics;
- construct hard negatives or preference pairs;
- manually edit, replace, or exclude samples to improve reported results.

Results may compare the predeclared V0 through V4 release stages, but a failure
observed on the Frozen Test Set is report-only. It must not become the rationale
for the next system change. Iteration and failure-case feedback use training and
development data instead.

## Human Evaluation

Reviewers see source context and randomized candidate order, but not generator,
ranker, platform title, or other reviewers' answers. They tag critical errors
before expressing preference.

Project developers may label directly verifiable content and integrity failures,
including semantic drift, genre hallucination, character-identity errors, plot
inconsistency, excessive clickbait, spoilers, generic titles, and duplicate
candidates. Developer judgments are not treated as ground truth for commercial
appeal among English readers.

When resources allow, independent English readers should perform blind
preference evaluation. This separately tests agreement among platform-published
titles, model rankings, and reader preferences.

The protocol should include:

- reviewer qualification and language expectations
- written rubric with positive and negative examples
- pilot calibration before production annotation
- duplicated items for within-reviewer consistency
- overlapping items for agreement measurement
- adjudication for critical disagreements

Platform-published titles are candidates or weak signals, not automatic ground
truth.

## Metrics

Primary quality metrics should be declared before each milestone. The initial
set is:

- pairwise accuracy against human preference
- NDCG at K for graded relevance
- Hit at 3 for acceptable candidates
- critical and major violation rate

Secondary diagnostics include candidate-order robustness, repeated-judge
agreement, subgroup performance by genre and strategy, candidate diversity,
latency, and estimated cost.

Published-title diagnostics use weak-label terminology:

- Published-title Top-1 Agreement
- Published-title Hit@3
- Mean Published-title Rank
- Platform Preference Agreement

These measurements quantify reproduction of an observed platform choice. They
must not be named translation accuracy or interpreted as proof of reader appeal,
CTR, paid conversion, or overall title quality.

## Robustness Checks

- randomly permute candidate order
- repeat stochastic judging with fixed recorded seeds where supported
- compare results with and without published-title anchors
- report performance by candidate generator
- inspect ties and near-ties separately
- test sensitivity to metric and rubric thresholds

## Statistical Reporting

Report the number of samples, candidates, and judgments with each result. Use
paired comparisons when methods rank the same candidate sets. Include uncertainty
through bootstrap confidence intervals or another predeclared method. Report both
effect size and interval, not only a significance threshold.

## Promotion Rule

A method advances only if it improves the declared primary metric, does not
increase critical violations, remains stable under candidate-order permutation,
and has a documented cost and latency tradeoff.

## Result Integrity

An evaluation report must identify dataset, candidate-set, label-set, ranker,
rubric, and metric versions. Any post-hoc exclusion or rubric change requires a
new report and a clear explanation.
