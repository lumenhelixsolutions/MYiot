# Start MYiot FastAPI hub (PowerShell 5.1+)
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot\..

if (-not (Test-Path ".\.venv\Scripts\python.exe")) {
    Write-Error "Virtual env not found. Run: python -m venv .venv; .\.venv\Scripts\pip install -r hub\requirements.txt"
}

$portInUse = Get-NetTCPConnection -LocalPort 8000 -State Listen -ErrorAction SilentlyContinue
if ($portInUse) {
    Write-Host "Port 8000 is already in use (PID $($portInUse.OwningProcess)). Hub may already be running." -ForegroundColor Yellow
    Write-Host "Open http://localhost:8000/health — or stop the other process and run this script again."
    exit 0
}

Set-Location .\hub
Write-Host "Starting MYiot hub on http://0.0.0.0:8000 ..."
& "..\.venv\Scripts\python.exe" -m uvicorn main:app --host 0.0.0.0 --port 8000 --reload