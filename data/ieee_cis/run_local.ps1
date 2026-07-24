$ErrorActionPreference = "Stop"

$ProjectRoot = Resolve-Path (Join-Path $PSScriptRoot "..\..")
$BundleRoot = $PSScriptRoot
$VenvPython = Join-Path $BundleRoot ".venv\Scripts\python.exe"
$RawDir = Join-Path $ProjectRoot "data\data\ieee-fraud-detection"
$OutputDir = Join-Path $ProjectRoot "data\processed\ieee_cis_spark"

if (-not (Test-Path $VenvPython)) {
    throw "Local environment not found. Run: .\data\ieee_cis\setup_local_windows.ps1"
}
if (-not (Test-Path (Join-Path $RawDir "train_transaction.csv"))) {
    throw "Raw IEEE-CIS data not found at $RawDir"
}

Push-Location $BundleRoot
try {
    # Attempt the complete Parquet output contract on Windows.
    $env:ENABLE_WINDOWS_PARQUET = "true"
    & $VenvPython -m pipeline.cli --raw-dir $RawDir --output-dir $OutputDir --master local[*]
    & $VenvPython -m pipeline.verify_processed --output-dir $OutputDir
}
finally {
    Pop-Location
}
