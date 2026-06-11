# ============================================================
# Skyro Local Dev Startup — runs backend-orders directly
# Usage: .\start-local.ps1
# ============================================================

Write-Host "Starting Skyro backend-orders on port 8000..." -ForegroundColor Cyan

$env:DATABASE_URL = "postgresql+asyncpg://skyro_admin:sky517227@skyro-db.cl4o2c2matz8.ap-south-1.rds.amazonaws.com:5432/skyro?sslmode=require"

Set-Location "$PSScriptRoot\backend-orders"

# Use project venv if available
if (Test-Path ".\dronw\Scripts\python.exe") {
    $python = ".\dronw\Scripts\python.exe"
} elseif (Test-Path ".\dron\Scripts\python.exe") {
    $python = ".\dron\Scripts\python.exe"
} else {
    $python = "python"
}

Write-Host "Python: $python" -ForegroundColor Gray
Write-Host "DB: AWS RDS PostgreSQL" -ForegroundColor Gray
Write-Host ""
Write-Host "API will be at: http://localhost:8000" -ForegroundColor Green
Write-Host "Press Ctrl+C to stop" -ForegroundColor Yellow
Write-Host ""

& $python -m uvicorn main:app --host 0.0.0.0 --port 8000 --reload
