"""
test_smoke.py — Smoke tests for backend-fleet-ai.

Run after starting all services:
    python test_smoke.py

Requires: pip install httpx
All tests are independent — a single failure does not abort the rest.
"""

import asyncio
import json
import sys
import httpx

BASE = "http://localhost:8002"


def passed(name: str) -> None:
    print(f"  [PASS] {name}")


def failed(name: str, detail: str) -> None:
    print(f"  [FAIL] {name}: {detail}")


async def test_root(client: httpx.AsyncClient) -> bool:
    r = await client.get(f"{BASE}/")
    ok = r.status_code == 200 and "Fleet AI" in r.text
    (passed if ok else failed)("GET / — service root", r.text[:80])
    return ok


async def test_fleet_status(client: httpx.AsyncClient) -> bool:
    r = await client.get(f"{BASE}/fleet-status")
    ok = r.status_code == 200
    if ok:
        data = r.json()
        ok = "drones" in data and "zones" in data and "conflicts" in data
    (passed if ok else failed)("GET /fleet-status", r.text[:120])
    return ok


async def test_assign_drone_no_drones(client: httpx.AsyncClient) -> bool:
    """Expect 503 when no drones are connected."""
    r = await client.post(f"{BASE}/assign-drone", json={
        "orderId": "ORD-SMOKE-1",
        "destination": "A",
        "priority": 1,
    })
    # 503 is expected when no drones are up; 200 is also valid if a drone is connected
    ok = r.status_code in (200, 503)
    (passed if ok else failed)(
        "POST /assign-drone (no drones → 503 or assigned → 200)", r.text[:120]
    )
    return ok


async def test_assign_drone_bad_destination(client: httpx.AsyncClient) -> bool:
    """Expect 4xx or 503 for an unknown destination."""
    r = await client.post(f"{BASE}/assign-drone", json={
        "orderId": "ORD-SMOKE-2",
        "destination": "ZZZ",
        "priority": 1,
    })
    ok = r.status_code in (400, 422, 503)
    (passed if ok else failed)("POST /assign-drone (bad destination)", r.text[:120])
    return ok


async def test_zone_status(client: httpx.AsyncClient) -> bool:
    r = await client.get(f"{BASE}/zone-status")
    ok = r.status_code == 200 and isinstance(r.json(), list)
    if ok:
        zones = [z["zone"] for z in r.json()]
        ok = "A" in zones and "B" in zones and "C" in zones
    (passed if ok else failed)("GET /zone-status", r.text[:120])
    return ok


async def test_reserve_landing(client: httpx.AsyncClient) -> bool:
    # First reservation should succeed
    r1 = await client.post(f"{BASE}/reserve-landing", json={
        "zone": "A",
        "droneId": "smoke-drone-1",
    })
    ok1 = r1.status_code == 200
    (passed if ok1 else failed)("POST /reserve-landing (first → 200)", r1.text[:120])

    # Second reservation should fail with 409
    r2 = await client.post(f"{BASE}/reserve-landing", json={
        "zone": "A",
        "droneId": "smoke-drone-2",
    })
    ok2 = r2.status_code == 409
    (passed if ok2 else failed)("POST /reserve-landing (duplicate → 409)", r2.text[:120])

    return ok1 and ok2


async def test_confirm_landing(client: httpx.AsyncClient) -> bool:
    # Confirm and release zone A (reserved in previous test)
    r = await client.post(f"{BASE}/landing/confirm", json={
        "zone": "A",
        "droneId": "smoke-drone-1",
        "landing_mode": "GPS",
        "offset_x": 0.0,
        "offset_y": 0.0,
    })
    ok = r.status_code == 200
    if ok:
        data = r.json()
        ok = data.get("occupied") is False
    (passed if ok else failed)("POST /landing/confirm (releases zone)", r.text[:120])
    return ok


async def test_conflicts(client: httpx.AsyncClient) -> bool:
    r = await client.get(f"{BASE}/conflicts")
    ok = r.status_code == 200
    if ok:
        data = r.json()
        ok = "conflicts" in data and "safe" in data
    (passed if ok else failed)("GET /conflicts", r.text[:120])
    return ok


async def test_authorize_denied(client: httpx.AsyncClient) -> bool:
    """Expect DENIED for a non-existent drone and order."""
    r = await client.post(f"{BASE}/authorize-mission", json={
        "droneId":     "ghost-drone",
        "orderId":     "ORD-DOES-NOT-EXIST",
        "destination": "A",
    })
    ok = r.status_code == 200
    if ok:
        data = r.json()
        ok = data.get("decision") in ("DENIED", "WAIT")
    (passed if ok else failed)(
        "POST /authorize-mission (invalid → DENIED/WAIT)", r.text[:180]
    )
    return ok


async def test_obstacle_alert(client: httpx.AsyncClient) -> bool:
    r = await client.post(f"{BASE}/obstacle-alert", json={
        "droneId":  "smoke-drone-1",
        "lat":      16.462,
        "lon":      80.508,
        "alt":      25.0,
        "severity": "MEDIUM",
    })
    ok = r.status_code == 200 and r.json().get("status") == "alert_received"
    (passed if ok else failed)("POST /obstacle-alert", r.text[:120])
    return ok


async def main() -> None:
    print("=" * 60)
    print(" Skyro Fleet AI — Smoke Test Suite")
    print(f" Target: {BASE}")
    print("=" * 60)

    results = []
    async with httpx.AsyncClient(timeout=10.0) as client:
        # Basic reachability first
        try:
            await client.get(f"{BASE}/")
        except Exception:
            print(f"\n[ERROR] Cannot reach {BASE}. Is the service running?\n")
            sys.exit(1)

        tests = [
            test_root,
            test_fleet_status,
            test_zone_status,
            test_assign_drone_no_drones,
            test_assign_drone_bad_destination,
            test_reserve_landing,
            test_confirm_landing,
            test_conflicts,
            test_authorize_denied,
            test_obstacle_alert,
        ]

        for t in tests:
            try:
                results.append(await t(client))
            except Exception as exc:
                failed(t.__name__, str(exc))
                results.append(False)

    passed_count = sum(results)
    total = len(results)
    print("-" * 60)
    print(f"\n  Results: {passed_count}/{total} tests passed\n")
    sys.exit(0 if passed_count == total else 1)


if __name__ == "__main__":
    asyncio.run(main())
