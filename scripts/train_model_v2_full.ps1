param(
    [ValidateSet("local", "cluster")]
    [string]$Mode = "local"
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Invoke-DockerComposeChecked {
    param(
        [Parameter(Mandatory = $true)]
        [string[]]$Args
    )

    & docker compose @Args
    if ($LASTEXITCODE -ne 0) {
        throw "docker compose $($Args -join ' ') failed with exit code $LASTEXITCODE"
    }
}

function Invoke-TrainingLocal {
    Write-Host "[v2] Falling back to local Docker training (Spark local[*])..."
    Invoke-DockerComposeChecked @("--profile", "training", "build", "model-training-local")

    Write-Host "[v2] Training baseline model (local)..."
    Invoke-DockerComposeChecked @("--profile", "training", "run", "--rm", "model-training-local", "uv", "run", "python", "-m", "fraud_model.train_baseline")

    Write-Host "[v2] Training comparison models (local)..."
    Invoke-DockerComposeChecked @("--profile", "training", "run", "--rm", "model-training-local", "uv", "run", "python", "-m", "fraud_model.train_compare")

    Write-Host "[v2] Training final tuned model (local)..."
    Invoke-DockerComposeChecked @("--profile", "training", "run", "--rm", "model-training-local", "uv", "run", "python", "-m", "fraud_model.tune_and_explain")
}

Write-Host "[v2] Building Docker training image..."
if ($Mode -eq "cluster") {
    Invoke-DockerComposeChecked @("--profile", "training", "build", "model-training")
}

if ($Mode -eq "cluster") {
    Write-Host "[v2] Starting Spark training cluster..."
    $clusterStarted = $true
    try {
        Invoke-DockerComposeChecked @("--profile", "training", "up", "-d", "spark-master", "spark-worker")
    }
    catch {
        $clusterStarted = $false
        Write-Warning "[v2] Spark cluster could not start. Reason: $($_.Exception.Message)"
    }

    if ($clusterStarted) {
        Write-Host "[v2] Training baseline model..."
        Invoke-DockerComposeChecked @("--profile", "training", "run", "--rm", "model-training", "uv", "run", "python", "-m", "fraud_model.train_baseline")

        Write-Host "[v2] Training comparison models..."
        Invoke-DockerComposeChecked @("--profile", "training", "run", "--rm", "model-training", "uv", "run", "python", "-m", "fraud_model.train_compare")

        Write-Host "[v2] Training final tuned model..."
        Invoke-DockerComposeChecked @("--profile", "training", "run", "--rm", "model-training", "uv", "run", "python", "-m", "fraud_model.tune_and_explain")
    }
    else {
        Invoke-TrainingLocal
    }
}
else {
    Invoke-TrainingLocal
}

Write-Host "[v2] Training completed. Expected artifacts:"
Write-Host "  - model/artifacts/v2/baseline_logreg_v2.joblib"
Write-Host "  - model/artifacts/v2/model_comparison_v2.json"
Write-Host "  - model/artifacts/v2/final_model_v2.joblib"
Write-Host "  - model/artifacts/v2/training_metadata_v2.json"
