$ErrorActionPreference = "Stop"
$Output = "data\processed\ieee_cis_fraud_risk\manifest.json"
if (-not (Test-Path $Output)) {
    throw "Processed data not found. Run docker compose -f docker-compose.preprocessing.yml run --rm preprocess first."
}
docker compose -f docker-compose.preprocessing.yml run --rm verify-processed
docker build -f docker\Dockerfile.processed-data -t fraud-risk-processed-data:1.0.0 .
