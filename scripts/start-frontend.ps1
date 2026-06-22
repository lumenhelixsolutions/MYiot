# Start MYiot Vite frontend (PowerShell 5.1+)
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot\..\app

if (-not (Test-Path ".\node_modules")) {
    Write-Host "Installing npm dependencies..."
    npm install
}

Write-Host "Starting frontend on http://localhost:5173 (proxies API to :8000)..."
npm run dev