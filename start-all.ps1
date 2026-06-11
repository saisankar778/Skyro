# ============================================================
# Skyro - Start ALL backends in one command
# Usage:  .\start-all.ps1
# ============================================================

$ROOT = $PSScriptRoot
$AWS_DB = "postgresql+asyncpg://skyro_admin:sky517227@skyro-db.cl4o2c2matz8.ap-south-1.rds.amazonaws.com:5432/skyro?sslmode=require"

function Find-Python($dir) {
    if (Test-Path "$dir\dronw\Scripts\python.exe") { return "$dir\dronw\Scripts\python.exe" }
    if (Test-Path "$dir\dron\Scripts\python.exe")  { return "$dir\dron\Scripts\python.exe" }
    return "python"
}

$py0 = Find-Python "$ROOT\backend-orders"
$py1 = Find-Python "$ROOT\backend"
$py2 = Find-Python "$ROOT\backend-fleet-ai"

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "   SKYRO - Starting All Backends" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# 1. backend-orders (port 8000)
Write-Host "[1/3] backend-orders   -> http://localhost:8000" -ForegroundColor Green
Start-Process powershell -ArgumentList "-NoExit", "-Command", "Write-Host 'backend-orders | port 8000' -ForegroundColor Green; cd '$ROOT\backend-orders'; `$env:DATABASE_URL='$AWS_DB'; & '$py0' -m uvicorn main:app --host 0.0.0.0 --port 8000 --reload"

Start-Sleep -Milliseconds 500

# 2. backend (Drone / MAVLink, port 8080)
Write-Host "[2/3] backend (drone)  -> http://localhost:8080" -ForegroundColor Yellow
Start-Process powershell -ArgumentList "-NoExit", "-Command", "Write-Host 'backend (drone) | port 8080' -ForegroundColor Yellow; cd '$ROOT\backend'; & '$py1' -m uvicorn main:app --host 0.0.0.0 --port 8080 --reload"

Start-Sleep -Milliseconds 500

# 3. backend-fleet-ai (port 8002)
Write-Host "[3/3] backend-fleet-ai -> http://localhost:8002" -ForegroundColor Magenta
Start-Process powershell -ArgumentList "-NoExit", "-Command", "Write-Host 'backend-fleet-ai | port 8002' -ForegroundColor Magenta; cd '$ROOT\backend-fleet-ai'; `$env:DATABASE_URL='$AWS_DB'; `$env:ORDERS_API_BASE='http://localhost:8000'; `$env:DRONE_BACKEND_URL='http://localhost:8080'; `$env:DRONE_BACKEND_WS='ws://localhost:8080/ws'; & '$py2' -m uvicorn main:app --host 0.0.0.0 --port 8002 --reload"

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  All 3 backends launching in new windows" -ForegroundColor Cyan
Write-Host ""
Write-Host "  Orders API   : http://localhost:8000/api/orders"       -ForegroundColor White
Write-Host "  Restaurants  : http://localhost:8000/api/restaurants"  -ForegroundColor White
Write-Host "  Drone API    : http://localhost:8080/"                 -ForegroundColor White
Write-Host "  Fleet AI     : http://localhost:8002/"                 -ForegroundColor White
Write-Host ""
Write-Host "  Close each PowerShell window to stop a service." -ForegroundColor Gray
Write-Host "========================================" -ForegroundColor Cyan
