# Configuration

Configuration files will describe reproducible choices, not contain executable
logic. Keep stable defaults separate from named experiment overrides.

Planned groups:

- data: dataset versions, split manifests, and validation policy
- generation: candidate strategies and provider-independent parameters
- constraints: enabled checks and severity policy
- ranking: method-specific settings
- evaluation: frozen-set version, metrics, and robustness checks
- experiments: small compositions of the groups above

Every run should save its fully resolved configuration. Do not store API keys,
tokens, local absolute paths, private dataset text, or machine-specific settings
here.

The single `title_selection.default.json` profile uses the OpenAI-compatible
chat-completions protocol. It resolves its model, endpoint, timeout, and
credential from `LLM_*` values in `.env` (or explicit process environment
variables). Never add an API key value to a checked-in configuration file.

Use descriptive experiment names such as `v1_pairwise_order_robustness` and add a
schema version whenever a configuration shape changes.
