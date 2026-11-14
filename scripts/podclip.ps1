# podclip launcher for Windows: runs the clipper inside its own private Python env.
$ErrorActionPreference = "Stop"
$EnvDir = Join-Path $HOME ".podcast-clipper\venv"
$Python = Join-Path $EnvDir "Scripts\python.exe"
$Here = Split-Path -Parent $MyInvocation.MyCommand.Path

if (-not (Test-Path $Python)) {
    Write-Host "Not set up yet. Run:  powershell -File `"$Here\setup.ps1`"" -ForegroundColor Red
    exit 1
}

& $Python (Join-Path $Here "run.py") @args
exit $LASTEXITCODE
