# start.ps1 — Start the Red Team service locally
# Usage: .\start.ps1  (run from D:\bling-red-team)

$ErrorActionPreference = "Stop"
$RedTeamDir = "$PSScriptRoot\red-team"

Write-Host ""
Write-Host "==================================================" -ForegroundColor Cyan
Write-Host "  BLING Red Team — Starting local stack" -ForegroundColor Cyan
Write-Host "==================================================" -ForegroundColor Cyan
Write-Host ""

# ── Step 1: Start Docker containers ─────────────────────────────────────────
Write-Host "[1/4] Starting Docker containers (postgres + redis)..." -ForegroundColor Yellow
Set-Location $RedTeamDir
docker-compose up -d
if ($LASTEXITCODE -ne 0) {
    Write-Host "ERROR: docker-compose up failed. Is Docker Desktop running?" -ForegroundColor Red
    exit 1
}

# ── Step 2: Wait for containers to be healthy ────────────────────────────────
Write-Host "[2/4] Waiting 5 seconds for containers to be healthy..." -ForegroundColor Yellow
Start-Sleep -Seconds 5

# ── Step 3: Activate venv ───────────────────────────────────────────────────
Write-Host "[3/4] Activating Python virtual environment..." -ForegroundColor Yellow
$VenvActivate = "$RedTeamDir\venv\Scripts\Activate.ps1"
if (-Not (Test-Path $VenvActivate)) {
    Write-Host "ERROR: venv not found at $VenvActivate" -ForegroundColor Red
    Write-Host "       Create it with: python -m venv venv && venv\Scripts\Activate.ps1 && pip install -r requirements.txt" -ForegroundColor Red
    exit 1
}
& $VenvActivate

# ── Step 4: Start uvicorn ────────────────────────────────────────────────────
Write-Host "[4/4] Starting uvicorn on http://localhost:8002 ..." -ForegroundColor Yellow
Write-Host ""
Write-Host "  Docs: http://localhost:8002/docs" -ForegroundColor Green
Write-Host "  Health: http://localhost:8002/health" -ForegroundColor Green
Write-Host ""
Write-Host "  Press Ctrl+C to stop uvicorn (then run .\stop.ps1 to tear down Docker)" -ForegroundColor DarkGray
Write-Host ""

# Open docs in browser after a short delay (background job)
Start-Job -ScriptBlock {
    Start-Sleep -Seconds 3
    Start-Process "http://localhost:8002/docs"
} | Out-Null

# Start uvicorn (blocking — runs in foreground so Ctrl+C works naturally)
Set-Location $RedTeamDir
python -m uvicorn app.main:app --host 0.0.0.0 --port 8002 --reload
