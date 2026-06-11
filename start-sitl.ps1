#!/usr/bin/env pwsh
# ============================================================
# start-sitl.ps1  — Launch multiple ArduPilot SITL instances on Windows
#
# Prerequisites:
#   1. WSL2 installed with Ubuntu  (or a native Linux box via SSH)
#   2. ArduPilot cloned inside WSL2: ~/ardupilot
#   3. ArduPilot SITL tools installed (Tools/autotest/sim_vehicle.py)
#
# Usage (from Skyro root):
#   .\start-sitl.ps1           # starts D-01 + D-02
#   .\start-sitl.ps1 -n 3      # starts D-01, D-02, D-03
#
# Each SITL instance sends MAVLink UDP to:
#   D-01  → localhost:14551
#   D-02  → localhost:14561
#   D-03  → localhost:14571
#   ...etc (each 10 ports apart)
#
# Your backend connects using:
#   D-01  → udpin://0.0.0.0:14551
#   D-02  → udpin://0.0.0.0:14561
#   D-03  → udpin://0.0.0.0:14571
# ============================================================

param (
    [int]$n = 2          # number of SITL drones to spawn
)

# Base SITL home location (SRM AP campus approximation)
$BASE_LAT  = 16.4628
$BASE_LON  = 80.5074
$BASE_ALT  = 25.0
$BASE_HEADING = 90

# Each drone gets a slightly different start position (offset 50m east per drone)
# and its own UDP output port
$BASE_PORT = 14551   # D-01 gets 14551, D-02 gets 14561, etc.

Write-Host ""
Write-Host "========================================"   -ForegroundColor Cyan
Write-Host "   SKYRO — Starting $n ArduPilot SITL Drone(s)"   -ForegroundColor Cyan
Write-Host "========================================"   -ForegroundColor Cyan
Write-Host ""

for ($i = 1; $i -le $n; $i++) {
    $droneId   = "D-0$i"
    $port      = $BASE_PORT + ($i - 1) * 10
    $instanceN = $i - 1           # ArduPilot --instance flag (0-indexed)
    $offsetLon = $BASE_LON + ($i - 1) * 0.0005   # ~50m east per drone

    # WSL command to launch one SITL instance in the background
    # --out sends MAVLink UDP packets to Windows host (127.0.0.1) on the target port
    $wslCmd = @"
cd ~/ardupilot && python Tools/autotest/sim_vehicle.py \
  -v ArduCopter \
  --instance $instanceN \
  --home=${BASE_LAT},${offsetLon},${BASE_ALT},${BASE_HEADING} \
  --out=udp:127.0.0.1:$port \
  --no-mavproxy \
  -S 5 \
  2>&1 | tee /tmp/sitl_drone_${i}.log
"@

    Write-Host "[$i/$n] Starting $droneId (instance=$instanceN, UDP port=$port) ..." -ForegroundColor Yellow
    Start-Process powershell -ArgumentList "-NoExit", "-Command", @"
Write-Host 'SITL $droneId | MAVLink -> localhost:$port' -ForegroundColor Yellow;
wsl bash -c '$wslCmd'
"@
    Start-Sleep -Milliseconds 3000   # stagger startup to avoid port races
}

Write-Host ""
Write-Host "========================================"   -ForegroundColor Cyan
Write-Host "  All $n SITL drones starting in WSL2"
Write-Host ""
Write-Host "  Wait ~30 seconds for GPS to lock, then"
Write-Host "  connect each drone in the Admin Dashboard:"
for ($i = 1; $i -le $n; $i++) {
    $port    = $BASE_PORT + ($i - 1) * 10
    $droneId = "D-0$i"
    Write-Host "    $droneId  →  udpin://0.0.0.0:$port"  -ForegroundColor Green
}
Write-Host ""
Write-Host "  Or run the batch connect below (copy into Admin console):"
Write-Host ""
$drones = @()
for ($i = 1; $i -le $n; $i++) {
    $port    = $BASE_PORT + ($i - 1) * 10
    $droneId = "D-0$i"
    $drones += "  { droneId: '$droneId', connectionString: 'udpin://0.0.0.0:$port' }"
}
Write-Host "  POST http://localhost:8080/api/drones/connect-batch" -ForegroundColor White
Write-Host "  Body: { drones: [" -ForegroundColor White
$drones | ForEach-Object { Write-Host $_ -ForegroundColor White }
Write-Host "  ] }" -ForegroundColor White
Write-Host ""
Write-Host "========================================"   -ForegroundColor Cyan
