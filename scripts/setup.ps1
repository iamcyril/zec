# scripts/setup.ps1 — Bootstrap Zecpath development environment (Windows PowerShell)
Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$RootDir = Split-Path -Parent $PSScriptRoot
Push-Location $RootDir

try {
    Write-Host "==> Creating virtual environment at .venv/" -ForegroundColor Cyan
    python -m venv .venv

    Write-Host "==> Upgrading pip" -ForegroundColor Cyan
    .\.venv\Scripts\python -m pip install --upgrade pip

    Write-Host "==> Installing dev dependencies" -ForegroundColor Cyan
    .\.venv\Scripts\pip install -r requirements-dev.txt

    Write-Host "==> Copying .env.example -> .env (if not present)" -ForegroundColor Cyan
    if (-Not (Test-Path ".env")) {
        Copy-Item ".env.example" ".env"
        Write-Host "    .env created." -ForegroundColor Green
    } else {
        Write-Host "    .env already exists, skipping." -ForegroundColor Yellow
    }

    Write-Host "==> Installing pre-commit hooks" -ForegroundColor Cyan
    .\.venv\Scripts\pre-commit install

    Write-Host ""
    Write-Host "Setup complete. Activate with:  .\.venv\Scripts\Activate.ps1" -ForegroundColor Green
} finally {
    Pop-Location
}
