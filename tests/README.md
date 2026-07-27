# Test Strategy

Tests will be added with implementation. The planned layers are:

| Layer | Protects |
| --- | --- |
| Contract tests | Schema compatibility and required provenance |
| Unit tests | Deterministic normalization, constraints, ranking, and metrics |
| Integration tests | Artifact handoff between adjacent pipeline stages |
| Regression tests | Known failure examples from the error taxonomy |
| Reproducibility tests | Stable splits, fingerprints, and seeded results |

Provider-backed tests must be opt-in, clearly marked, and excluded from the
default offline suite. Synthetic examples should cover public tests; private
dataset text must not be copied into fixtures.
