# stop.ps1 — Stop the Red Team service and Docker containers
# Usage: .\stop.ps1  (run from D:\bling-red-team)

$ErrorActionPreference = "SilentlyContinue"
$RedTeamDir = "$PSScriptRoot\red-team"

Write-Host ""
Write-Host "==================================================" -ForegroundColor Cyan
Write-Host "  BLING Red Team — Stopping local stack" -ForegroundColor Cyan
Write-Host "==================================================" -ForegroundColor Cyan
Write-Host ""

# ── Step 1: Kill any process listening on port 8002 (uvicorn) ───────────────
Write-Host "[1/2] Stopping uvicorn on port 8002..." -ForegroundColor Yellow

$procs = netstat -ano | Select-String ":8002 " | ForEach-Object {
    ($_ -split "\s+")[-1]
} | Sort-Object -Unique | Where-Object { $_ -match "^\d+$" }

if ($procs) {
    foreach ($pid in $procs) {
        $p = Get-Process -Id $pid -ErrorAction SilentlyContinue
        if ($p) {
            Write-Host "  Killing PID $pid ($($p.Name))..." -ForegroundColor DarkGray
            Stop-Process -Id $pid -Force -ErrorAction SilentlyContinue
        }
    }
    Start-Sleep -Milliseconds 500
    Write-Host "  uvicorn stopped." -ForegroundColor Green
} else {
    Write-Host "  No process found on port 8002 (already stopped)." -ForegroundColor DarkGray
}

# ── Step 2: Stop Docker containers ──────────────────────────────────────────
Write-Host "[2/2] Stopping Docker containers..." -ForegroundColor Yellow
Set-Location $RedTeamDir
docker-compose down
if ($LASTEXITCODE -ne 0) {
    Write-Host "  WARNING: docker-compose down returned a non-zero exit code." -ForegroundColor DarkYellow
    Write-Host "           Containers may still be running — check Docker Desktop." -ForegroundColor DarkYellow
} else {
    Write-Host "  Docker containers stopped." -ForegroundColor Green
}

Write-Host ""
Write-Host "Red Team stopped cleanly." -ForegroundColor Green
Write-Host ""
