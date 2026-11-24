$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path

Write-Host "=== ChemMat Studio One-Click Launcher ===" -ForegroundColor Cyan

if (-not (Test-Path "$Root\frontend\dist\index.html")) {
  Write-Host "Building frontend production bundle..." -ForegroundColor Yellow
  Push-Location "$Root\frontend"
  if (-not (Test-Path "node_modules")) { npm install }
  npm run build
  Pop-Location
}

Write-Host "Syncing Python scientific backend..." -ForegroundColor Yellow
Push-Location "$Root\backend"
uv sync
Write-Host "Starting ChemMat Studio at http://127.0.0.1:8000 ..." -ForegroundColor Green
Start-Process "http://127.0.0.1:8000"
uv run uvicorn app.main:app --host 127.0.0.1 --port 8000
Pop-Location
