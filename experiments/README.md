# Experiments

This directory records reviewed experiment definitions and concise reports. Large
outputs belong in the ignored `runs/` or `artifacts/` directories.

Each experiment should include:

- a unique ID and short research question
- links to immutable input fingerprints
- the resolved configuration
- environment and model or prompt versions
- seeds and retry policy
- declared primary and secondary metrics
- a short result, limitations, and decision

Recommended naming:

```text
YYYYMMDD_stage_question/
|-- manifest.yaml
`-- report.md
```

Do not overwrite a completed experiment. Create a successor and state what
changed. Failed and negative experiments remain useful and should be recorded
when they influence later decisions.
