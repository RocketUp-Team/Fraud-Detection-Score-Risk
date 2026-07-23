$ErrorActionPreference = "Stop"
$manifest = "data\processed\ieee_cis_spark\manifest.json"
if (-not (Test-Path $manifest)) {
    throw "Processed data not found. Run the preprocess service first: docker compose -f docker-compose.preprocessing.yml run --rm preprocess"
}
docker build -f docker/Dockerfile.processed-data -t ieee-cis-processed-data:latest .
