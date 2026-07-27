# Evaluation Protocol

## Purpose

This protocol ensures that improvements reflect better ranking rather than a
changed candidate pool, leaked labels, or unstable judge behavior.

## Evaluation Sets

Use three distinct sets:

| Set | Purpose | Tuning allowed |
| --- | --- | --- |
| Development | Rubric, prompts, rules, and diagnostics | Yes |
| Validation | Method selection and threshold decisions | Limited |
| Frozen evaluation | Final comparison and reporting | No |

The frozen set is versioned, fingerprinted, grouped to prevent related-title
leakage, and opened only for scheduled milestone evaluations.

## Human Evaluation

Reviewers see source context and randomized candidate order, but not generator,
ranker, platform title, or other reviewers' answers. They tag critical errors
before expressing preference.

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

Primary metrics should be declared before each milestone. The initial set is:

- pairwise accuracy against human preference
- NDCG at K for graded relevance
- Hit at 3 for acceptable candidates
- critical and major violation rate

Secondary diagnostics include candidate-order robustness, repeated-judge
agreement, subgroup performance by genre and strategy, candidate diversity,
latency, and estimated cost.

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
