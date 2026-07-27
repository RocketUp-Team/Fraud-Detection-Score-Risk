param(
    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]]$PipelineArgs
)

$ErrorActionPreference = "Stop"

docker compose -f docker-compose.preprocessing.yml build
docker compose -f docker-compose.preprocessing.yml run --rm preprocess @PipelineArgs
docker compose -f docker-compose.preprocessing.yml run --rm verify-processed
