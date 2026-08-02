[CmdletBinding()]
param(
    [string]$InputPath = "data/batch_tests/novel_pairs_100_request_inputs.jsonl",
    [string]$OutputPath = "data/batch_tests/novel_pairs_100_validation_output.jsonl",
    [string]$ReportPath = "data/batch_tests/novel_pairs_100_batch_test_report.json"
)

$ProjectRoot = Split-Path -Parent $PSScriptRoot
$PythonPath = Join-Path $ProjectRoot ".venv/Scripts/python.exe"
if (-not (Test-Path -LiteralPath $PythonPath)) {
    $PythonPath = "python"
}

& $PythonPath (Join-Path $PSScriptRoot "run_novel_pair_batch_test.py") `
    --input (Join-Path $ProjectRoot $InputPath) `
    --output (Join-Path $ProjectRoot $OutputPath) `
    --report (Join-Path $ProjectRoot $ReportPath)
exit $LASTEXITCODE
