# Runs every project check (ruff, format, pytest, the phase 4 to 6 checks, dashboard build and tests)
# with the Python environment in .venv. Takes a few minutes.
#
#   scripts\check.ps1

$ErrorActionPreference = "Stop"
$Repo = Split-Path -Parent $PSScriptRoot
$VenvPython = Join-Path $Repo ".venv\Scripts\python.exe"

if (-not (Test-Path $VenvPython)) {
    Write-Host "ERROR: The Python environment is missing. Run scripts\setup.ps1 first." -ForegroundColor Red
    exit 1
}

Set-Location $Repo
& $VenvPython scripts\run_checks.py
exit $LASTEXITCODE
