$ErrorActionPreference = "Stop"

$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $ProjectRoot

if (-not (Get-Command java -ErrorAction SilentlyContinue)) {
    Write-Host "Java 17 is not available in PATH." -ForegroundColor Yellow
    Write-Host "Install it with:" -ForegroundColor Yellow
    Write-Host "  winget install EclipseAdoptium.Temurin.17.JDK" -ForegroundColor Cyan
    Write-Host "Then restart PowerShell / VS Code and run this script again." -ForegroundColor Yellow
    exit 1
}

$VenvPython = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
if (-not (Test-Path $VenvPython)) {
    Write-Host "Creating .venv with Python 3.11..."
    py -3.11 -m venv .venv
}

& $VenvPython -m pip install --upgrade pip setuptools wheel
& $VenvPython -m pip install -r requirements.local.txt
& $VenvPython -m ipykernel install --user --name fraud-detection-spark --display-name "Python (Fraud Spark)"

Write-Host ""
Write-Host "Local Spark environment is ready." -ForegroundColor Green
Write-Host "In VS Code/Jupyter, select kernel: Python (Fraud Spark)" -ForegroundColor Green
Write-Host "Active interpreter: $VenvPython"
