param(
    [ValidateSet("local", "cluster")]
    [string]$Mode = "local",
    [string]$TrainingVersion = "",
    [string]$DataRoot = "ieee_cis_fraud_risk"
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
        -e FRAUD_MODEL_DATA_ROOT=$ContainerDataRoot `
        -e FRAUD_GIT_COMMIT=$GitCommit `
        -e FRAUD_GIT_DIRTY=$GitDirty `
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

function Resolve-ContainerDataRoot {
    param([string]$RequestedPath)

    $projectRoot = Split-Path -Parent $PSScriptRoot
    $processedRoot = [System.IO.Path]::GetFullPath(
        (Join-Path $projectRoot "data\processed")
    )
    if ([System.IO.Path]::IsPathRooted($RequestedPath)) {
        $hostPath = [System.IO.Path]::GetFullPath($RequestedPath)
    } elseif (
        $RequestedPath -like "data\processed\*" -or
        $RequestedPath -like "data/processed/*"
    ) {
        $hostPath = [System.IO.Path]::GetFullPath(
            (Join-Path $projectRoot $RequestedPath)
        )
    } else {
        $hostPath = [System.IO.Path]::GetFullPath(
            (Join-Path $processedRoot $RequestedPath)
        )
    }
    if (-not (Test-Path -LiteralPath $hostPath -PathType Container)) {
        throw "Training data root does not exist: $hostPath"
    }
    $relative = [System.IO.Path]::GetRelativePath($processedRoot, $hostPath)
    if ($relative -eq ".." -or $relative.StartsWith("..$([System.IO.Path]::DirectorySeparatorChar)")) {
        throw "Training data root must stay under $processedRoot"
    }
    return "/data/processed/" + ($relative -replace "\\", "/")
}

$ContainerDataRoot = Resolve-ContainerDataRoot $DataRoot
$GitCommit = (& git rev-parse HEAD).Trim()
if ($LASTEXITCODE -ne 0 -or -not $GitCommit) {
    throw "Could not resolve Git commit for training lineage"
}
$GitDirty = if (& git status --porcelain) { "true" } else { "false" }

function Invoke-Workflow {
    param([Parameter(Mandatory = $true)][string]$Service)

    $stages = @(
        "validate_data",
        "train_baseline",
        "train_compare",
        "tune_and_explain",
        "threshold_analysis",
        "evaluate_holdout",
        "package_candidate",
        "promotion_gate"
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
    Write-Host "[training] Building and starting Spark cluster..."
    & docker compose --profile training build model-training
    if ($LASTEXITCODE -ne 0) {
        throw "Could not build model-training image"
    }
    & docker compose --profile training up -d spark-master spark-worker
    if ($LASTEXITCODE -ne 0) {
        throw "Could not start Spark standalone cluster"
    }
    Invoke-Workflow -Service "model-training"
} else {
    Invoke-Local
}

Write-Host "[training] Completed successfully."
Write-Host "[training] Model artifacts: model/artifacts/$TrainingVersion/"
Write-Host "[training] MLflow database: model/artifacts/mlflow.db"
Write-Host "[training] Data root in container: $ContainerDataRoot"
