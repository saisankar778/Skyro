#!/usr/bin/env python3
"""
sitl_sim_windows.py — Lightweight multi-drone simulator for Windows

Simulates N drones on Skyro WITHOUT needing ArduPilot, WSL2, or MAVSDK.
Works by injecting simulated drone state directly into the drone backend
via the /api/sim/inject-drone endpoint. The WS broadcaster then includes
them in every broadcast, and fleet-ai picks them up as real IDLE drones.

Usage:
    python sitl_sim_windows.py             # 2 drones
    python sitl_sim_windows.py --drones 3  # 3 drones

After running, you should see:
  ✅ D-01  IDLE  battery=85.0%
  ✅ D-02  IDLE  battery=82.3%
  ...

The drones will appear in the Admin Dashboard map and can be assigned orders.
Press Ctrl+C to stop the simulation.

NOTE: This is for testing/demo only. For real drone flights, connect ArduPilot
      SITL instances using the start-sitl.ps1 script (requires WSL2).
"""

import asyncio
import math
import random
import time
import argparse
import logging
import httpx

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("sitl_sim")

# SRM AP campus base coordinates
BASE_LAT = 16.462635
BASE_LON = 80.506471
LON_OFFSET_PER_DRONE = 0.00045  # ~50m east per drone

DRONE_IDS = ["D-01", "D-02", "D-03", "D-04", "D-05"]


class SimulatedDrone:
    """Simulates one drone's telemetry."""

    def __init__(self, drone_id: str, index: int):
        self.drone_id = drone_id
        self.lat = BASE_LAT
        self.lon = BASE_LON + index * LON_OFFSET_PER_DRONE
        self.alt = 0.0
        self.battery = round(80.0 + random.uniform(-10, 10), 1)
        self.status = "IDLE"
        self.armed = False
        self.mode = "READY"
        self._last_update = time.monotonic()

    def to_dict(self) -> dict:
        return {
            "drone_id": self.drone_id,
            "lat": round(self.lat, 7),
            "lon": round(self.lon, 7),
            "alt": round(self.alt, 2),
            "battery": round(self.battery, 1),
            "status": self.status,
            "armed": self.armed,
            "mode": self.mode,
        }

    def tick(self, dt: float):
        """Simulate small GPS jitter and slow battery drain."""
        self.lat += random.gauss(0, 0.0000008)
        self.lon += random.gauss(0, 0.0000008)
        self.battery = max(5.0, self.battery - dt * 0.005)  # very slow drain


async def inject_drone(client: httpx.AsyncClient, drone: SimulatedDrone, backend: str) -> bool:
    """Push drone telemetry to the drone backend's sim inject endpoint."""
    try:
        r = await client.post(
            f"{backend}/api/sim/inject-drone",
            json=drone.to_dict(),
            timeout=5.0,
        )
        if r.status_code == 200:
            return True
        else:
            logger.warning(f"[{drone.drone_id}] inject-drone → {r.status_code}: {r.text[:80]}")
            return False
    except httpx.ConnectError:
        logger.error(f"[{drone.drone_id}] Cannot reach backend at {backend}. Is the backend running?")
        return False
    except Exception as e:
        logger.warning(f"[{drone.drone_id}] inject error: {e}")
        return False


async def run_drone(drone: SimulatedDrone, backend: str):
    """Main loop for one simulated drone: inject every 2 seconds."""
    async with httpx.AsyncClient() as client:
        while True:
            now = time.monotonic()
            dt = now - drone._last_update
            drone._last_update = now
            drone.tick(dt)

            await inject_drone(client, drone, backend)
            logger.debug(
                f"[{drone.drone_id}] lat={drone.lat:.6f} lon={drone.lon:.6f} "
                f"bat={drone.battery:.1f}% status={drone.status}"
            )
            await asyncio.sleep(2.0)


async def check_fleet_ai(fleet_ai: str) -> dict:
    """Check what drones fleet-ai can see."""
    try:
        async with httpx.AsyncClient() as client:
            r = await client.get(f"{fleet_ai}/api/sim/fleet-state", timeout=5.0)
            if r.status_code == 200:
                return r.json()
    except Exception:
        pass
    return {}


async def main(n_drones: int, backend: str, fleet_ai: str):
    print()
    print("=" * 55)
    print(f"   SKYRO SITL SIMULATOR — {n_drones} Drone(s)")
    print("=" * 55)
    print(f"   Backend  : {backend}")
    print(f"   Fleet AI : {fleet_ai}")
    print()

    drones = [SimulatedDrone(DRONE_IDS[i], i) for i in range(n_drones)]

    # Initial injection
    print("Injecting drones into backend...")
    async with httpx.AsyncClient() as client:
        for drone in drones:
            ok = await inject_drone(client, drone, backend)
            symbol = "✅" if ok else "❌"
            print(f"  {symbol} {drone.drone_id}  IDLE  battery={drone.battery}%  lat={drone.lat:.5f}")

    print()
    print("Waiting 3 seconds for fleet-ai to pick up state via WebSocket...")
    await asyncio.sleep(3.0)

    # Check fleet-ai
    state = await check_fleet_ai(fleet_ai)
    if state:
        drones_visible = state.get("count", 0)
        print(f"✅ Fleet AI sees {drones_visible} drone(s).")
    else:
        print("⚠️  Fleet AI not responding — orders may not be assignable yet.")
        print("   Make sure fleet-ai is running at:", fleet_ai)

    print()
    print("Simulation running. Drones update every 2 seconds.")
    print("You can now place orders in the app — drones will be assigned automatically.")
    print("Press Ctrl+C to stop.")
    print()

    # Run all drones concurrently
    tasks = [asyncio.create_task(run_drone(drone, backend)) for drone in drones]
    try:
        await asyncio.gather(*tasks)
    except asyncio.CancelledError:
        pass
    except KeyboardInterrupt:
        pass
    finally:
        for task in tasks:
            task.cancel()
        print("\nSimulation stopped.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Skyro Windows SITL Simulator — no ArduPilot/WSL needed"
    )
    parser.add_argument(
        "--drones", type=int, default=2,
        help="Number of drones to simulate (1-5, default: 2)"
    )
    parser.add_argument(
        "--backend", type=str, default="http://localhost:8080",
        help="Drone backend URL (default: http://localhost:8080)"
    )
    parser.add_argument(
        "--fleet-ai", type=str, default="http://localhost:8002",
        help="Fleet AI URL (default: http://localhost:8002)"
    )
    args = parser.parse_args()
    n = min(max(args.drones, 1), len(DRONE_IDS))

    try:
        asyncio.run(main(n, args.backend, args.fleet_ai))
    except KeyboardInterrupt:
        print("\nStopped.")
