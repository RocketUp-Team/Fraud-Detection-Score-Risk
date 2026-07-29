param(
    [ValidateSet("local", "cluster")]
    [string]$Mode = "local",
    [string]$TrainingVersion = ""
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Invoke-Stage {
    param(
        [Parameter(Mandatory = $true)][string]$Service,
        [Parameter(Mandatory = $true)][string]$Module
    )

    Write-Host "[training] $Module ($Service, version=$TrainingVersion)"
    & docker compose --profile training run --rm `
        -e FRAUD_MODEL_TRAINING_VERSION=$TrainingVersion `
        -e MLFLOW_EXPERIMENT=fraud-detection-training `
        $Service uv run python -m fraud_model.$Module
    if ($LASTEXITCODE -ne 0) {
        throw "Training stage '$Module' failed with exit code $LASTEXITCODE"
    }
}

function Resolve-TrainingVersion {
    param([string]$RequestedVersion)
    if ($RequestedVersion) { return $RequestedVersion }

    $artifactRoot = Join-Path (Split-Path -Parent $PSScriptRoot) "model\artifacts"
    $versions = @(
        Get-ChildItem -LiteralPath $artifactRoot -Directory -ErrorAction SilentlyContinue |
            Where-Object { $_.Name -match '^\d+\.\d+\.\d+$' } |
            ForEach-Object { [version]$_.Name }
    )
    if ($versions.Count -eq 0) { return "0.0.1" }
    $next = ($versions | Sort-Object -Descending | Select-Object -First 1)
    return "$($next.Major).$($next.Minor).$($next.Build + 1)"
}

$TrainingVersion = Resolve-TrainingVersion $TrainingVersion

function Invoke-Workflow {
    param([Parameter(Mandatory = $true)][string]$Service)

    $stages = @(
        "validate_data",
        "train_baseline",
        "train_compare",
        "tune_and_explain",
        "threshold_analysis",
        "evaluate_holdout"
    )
    foreach ($stage in $stages) {
        Invoke-Stage -Service $Service -Module $stage
    }
}

function Invoke-Local {
    Write-Host "[training] Building local Spark Docker image..."
    & docker compose --profile training build model-training-local
    if ($LASTEXITCODE -ne 0) {
        throw "Could not build model-training-local image"
    }
    Invoke-Workflow -Service "model-training-local"
}

if ($Mode -eq "cluster") {
    Write-Host "[training] Trying Spark cluster..."
    $clusterReady = $true
    & docker compose --profile training build model-training
    if ($LASTEXITCODE -ne 0) { $clusterReady = $false }
    if ($clusterReady) {
        & docker compose --profile training up -d spark-master spark-worker
        if ($LASTEXITCODE -ne 0) { $clusterReady = $false }
    }

    if ($clusterReady) {
        Invoke-Workflow -Service "model-training"
    } else {
        Write-Warning "Spark cluster unavailable; falling back to Spark local[*]."
        Invoke-Local
    }
} else {
    Invoke-Local
}

Write-Host "[training] Completed successfully."
Write-Host "[training] Model artifacts: model/artifacts/$TrainingVersion/"
Write-Host "[training] MLflow history: model/artifacts/mlruns/"
