param(
    [ValidatePattern("^[a-zA-Z0-9._-]+$")]
    [string]$CandidateName = "ieee_cis_fraud_risk_2_1_0"
)

$ErrorActionPreference = "Stop"
$containerOutput = "/app/data/processed/candidates/$CandidateName"

docker compose -f docker-compose.preprocessing.yml build
if ($LASTEXITCODE -ne 0) {
    throw "Could not build preprocessing image"
}
docker compose -f docker-compose.preprocessing.yml run --rm `
    -e IEEE_CIS_OUTPUT_DIR=$containerOutput `
    preprocess
if ($LASTEXITCODE -ne 0) {
    throw "Preprocessing failed; stable processed data was not changed"
}
docker compose -f docker-compose.preprocessing.yml run --rm `
    verify-processed `
    --output-dir $containerOutput
if ($LASTEXITCODE -ne 0) {
    throw "Candidate verification failed; stable processed data was not changed"
}

Write-Host "[preprocessing] Candidate ready at data/processed/candidates/$CandidateName"
