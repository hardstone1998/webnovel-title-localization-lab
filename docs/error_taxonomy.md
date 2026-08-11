# Error Taxonomy

The taxonomy separates factual or safety-like violations from preference
failures. A candidate may receive multiple tags.

## Severity

| Level | Meaning | Ranking treatment |
| --- | --- | --- |
| Critical | Invents or reverses a central premise | Reject |
| Major | Materially misleads genre, character, or hook | Strong penalty |
| Minor | Reduces fluency, style fit, or distinctiveness | Preference signal |
| Note | Debatable issue worth reviewer discussion | No automatic penalty |

## Error Codes

| Code | Category | Definition |
| --- | --- | --- |
| SEMANTIC_MISMATCH | Semantic mismatch | Changes the core premise or causal relationship |
| ENTITY_ERROR | Protagonist or relationship error | Assigns the wrong identity, role, gender, or relationship |
| GENRE_MISMATCH | Genre mismatch | Signals a genre or tone unsupported by the story |
| HOOK_INVENTED | Misleading hook | Adds a power, event, or promise absent from the source |
| SPOILER_RISK | Spoiler risk | Reveals a late or intentionally hidden development |
| CLICKBAIT_EXCESS | Excessive hype | Uses unsupported superlatives or sensational framing |
| TOO_LITERAL | Over-literal rendering | Preserves source structure at the cost of English readability |
| UNNATURAL_ENGLISH | English quality | Contains awkward grammar, collocation, or title casing |
| STYLE_MISMATCH | Platform style mismatch | Misses the declared target-platform convention |
| LOW_DISTINCTIVENESS | Generic title | Could apply to many unrelated stories |
| DUPLICATE_CANDIDATE | Low candidate diversity | Is effectively equivalent to another candidate in the set |
| LENGTH_MISMATCH | Poor title length | Is impractical or inconsistent with the chosen title strategy |

## Annotation Rules

Reviewers first judge critical and major errors without seeing model identity or
ranking position. Preference dimensions are scored only after violation tagging.
When evidence is insufficient, reviewers should mark the item for adjudication
rather than infer missing story facts.

Each annotation records the error code, severity, short rationale, evidence field
from the source record, rubric version, and reviewer class.

## Annotator Scope

Project developers may annotate errors that can be checked against the source
record: semantic drift, unsupported genre or abilities, character identity and
relationship errors, plot inconsistency, excessive clickbait, spoilers, generic
titles, and candidate duplication. Duplicate detection should also be automated
where normalization makes it deterministic.

Developer labels are validity and diagnostic evidence. Because project
developers are not assumed to represent the target English readership, their
personal appeal judgments must not be promoted to ground truth for commercial
attractiveness or reader preference.

Independent English readers should be used for blind preference evaluation when
available. Their candidate order is randomized, and generator identity, ranker
output, Platform Anchor, and other reviewers' decisions remain hidden.

## Reporting

Reports should show candidate-level and sample-level error rates, co-occurring
errors, disagreement rates, and error distribution by genre and generation
strategy. Aggregate quality scores must not hide critical violation counts.
