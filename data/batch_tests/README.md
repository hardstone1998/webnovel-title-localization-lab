# Version-controlled batch test data

`novel_pairs_100_request_inputs.jsonl` is the checked-in request input created
from the local novel-pair data. Each record contains only `pair_id` and the
three request parameters: `author_zh`, `zh_synopsis`, and `genre_zh`.

Run `scripts/run_novel_pairs_100_batch_test.ps1` to validate that input. The
script regenerates these checked-in outputs deterministically:

- `novel_pairs_100_validation_output.jsonl`: one `passed` result per `pair_id`
- `novel_pairs_100_batch_test_report.json`: run summary and record count

Review and commit any intentional data or output changes together.
