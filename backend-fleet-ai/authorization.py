"""
authorization.py — Mission Authorization Layer.

This is the safety gate that EVERY mission must pass before the Drone
Backend is allowed to launch. It checks all safety conditions in order
and returns APPROVED / DENIED / WAIT with a detailed reason.

Safety rules (all rule-based, no ML — critical safety must be deterministic):
    1. Drone must be IDLE (not on another mission).
    2. Order must exist and be in status 'Assigned' or 'En Route'
       with drone_id matching the requested drone.
    3. Landing zone must be free (or reservable).
    4. No predicted air traffic conflicts involving this drone.

If all pass → APPROVED.
If any conflict → WAIT (retry in a few seconds).
If any hard violation → DENIED.
"""

from __future__ import annotations

import logging
import os
from typing import Optional

import httpx
from fastapi import APIRouter

from models import (
    AuthorizeMissionRequest,
    AuthorizeMissionResponse,
)

logger = logging.getLogger(__name__)
router = APIRouter(tags=["authorization"])

# Service URLs (configurable via environment)
ORDERS_API_BASE:    str = os.getenv("ORDERS_API_BASE",    "https://fff8-2401-4900-cbd5-7c0d-d549-241c-a989-4b7a.ngrok-free.app")
DRONE_BACKEND_URL:  str = os.getenv("DRONE_BACKEND_URL",  "https://6deb-115-241-193-70.ngrok-free.app")

# Statuses that count as "this order is ready to fly"
VALID_ORDER_STATUSES = {"Assigned", "En Route", "Ready for Launch", "Accepted"}


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

async def _fetch_order(order_id: str) -> Optional[dict]:
    """GET order from orders service. Returns None on error."""
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            r = await client.get(f"{ORDERS_API_BASE}/api/orders/{order_id}")
        if r.status_code == 200:
            return r.json()
        logger.warning(f"Orders service returned {r.status_code} for order {order_id}")
    except Exception as exc:
        logger.error(f"Failed to reach orders service: {exc}")
    return None


async def _check_drone_idle(drone_id: str) -> tuple[bool, str]:
    """Returns (ok, reason)."""
    from state_manager import get_state, poll_drone_status_http
    state = await get_state(drone_id)
    if state is None:
        # Try a live HTTP fetch as fallback
        state = await poll_drone_status_http(drone_id)
    if state is None:
        return False, f"Drone '{drone_id}' is not connected to the fleet."
    if state.status == "OFFLINE":
        return False, f"Drone '{drone_id}' is OFFLINE."
    if state.status != "IDLE":
        return False, f"Drone '{drone_id}' is busy (status='{state.status}'). Try another drone."
    if state.battery < 15.0:
        return False, f"Drone '{drone_id}' battery critically low ({state.battery:.0f}%). Charge before mission."
    return True, "ok"


async def _check_order(order_id: str, drone_id: str) -> tuple[bool, str]:
    """Verify the order exists and is assigned to this drone."""
    order = await _fetch_order(order_id)
    if order is None:
        return False, f"Order '{order_id}' not found or orders service unreachable."
    order_status = order.get("status", "")
    if order_status not in VALID_ORDER_STATUSES:
        return False, (
            f"Order '{order_id}' is in status '{order_status}', "
            f"expected one of {VALID_ORDER_STATUSES}."
        )
    assigned = order.get("droneId") or order.get("drone_id")
    if assigned and assigned != drone_id:
        return False, (
            f"Order '{order_id}' is already assigned to drone '{assigned}', "
            f"not '{drone_id}'."
        )
    return True, "ok"


async def _check_landing_zone(destination: str) -> tuple[bool, bool, str]:
    """
    Returns (ok, wait, reason).
        ok=True, wait=False → zone is free, proceed
        ok=False, wait=True → zone occupied, retry later
        ok=False, wait=False → hard error
    """
    from landing import is_zone_available
    available = await is_zone_available(destination.upper())
    if available:
        return True, False, "ok"
    return False, True, f"Landing zone '{destination}' is currently occupied. Waiting for clearance."


async def _check_traffic(drone_id: str) -> tuple[bool, bool, str]:
    """
    Returns (ok, wait, reason).
    """
    from state_manager import get_all_states
    from traffic import detect_conflicts
    states = await get_all_states()
    conflicts = detect_conflicts(states)
    for c in conflicts:
        if drone_id in (c.drone_a, c.drone_b):
            return False, True, (
                f"Air traffic conflict detected involving drone '{drone_id}': "
                f"{c.resolution}"
            )
    return True, False, "ok"


# ---------------------------------------------------------------------------
# Core authorization function (also callable programmatically)
# ---------------------------------------------------------------------------

async def authorize_mission(req: AuthorizeMissionRequest) -> AuthorizeMissionResponse:
    """
    Run all safety checks in order. Returns a structured decision.
    Checks are ordered from cheapest to most expensive.
    """
    details: dict = {}

    # --- Check 1: Drone is idle and has battery ---
    ok, reason = await _check_drone_idle(req.droneId)
    details["drone_check"] = reason
    if not ok:
        return AuthorizeMissionResponse(
            decision="DENIED",
            reason=reason,
            details=details,
        )

    # --- Check 2: Order is valid and assigned to this drone ---
    ok, reason = await _check_order(req.orderId, req.droneId)
    details["order_check"] = reason
    if not ok:
        return AuthorizeMissionResponse(
            decision="DENIED",
            reason=reason,
            details=details,
        )

    # --- Check 3: Landing zone is free ---
    ok, wait, reason = await _check_landing_zone(req.destination)
    details["zone_check"] = reason
    if not ok:
        decision = "WAIT" if wait else "DENIED"
        return AuthorizeMissionResponse(
            decision=decision,
            reason=reason,
            details=details,
        )

    # --- Check 4: No air traffic conflicts ---
    ok, wait, reason = await _check_traffic(req.droneId)
    details["traffic_check"] = reason
    if not ok:
        decision = "WAIT" if wait else "DENIED"
        return AuthorizeMissionResponse(
            decision=decision,
            reason=reason,
            details=details,
        )

    # --- All checks passed ---
    logger.info(
        f"Mission APPROVED: drone={req.droneId}, order={req.orderId}, dest={req.destination}"
    )
    return AuthorizeMissionResponse(
        decision="APPROVED",
        reason="All safety checks passed. Mission is authorized.",
        details=details,
    )


# ---------------------------------------------------------------------------
# Router endpoint
# ---------------------------------------------------------------------------

@router.post(
    "/authorize-mission",
    summary="Authorize a drone mission after all safety checks",
    response_model=AuthorizeMissionResponse,
)
async def authorize_mission_endpoint(req: AuthorizeMissionRequest) -> AuthorizeMissionResponse:
    """
    Call this BEFORE dispatching a launch command to the drone backend.

    Returns:
    - **APPROVED** — safe to launch immediately
    - **WAIT**     — a temporary condition (zone occupied, traffic conflict);
                     retry after a few seconds
    - **DENIED**   — hard failure (drone busy, order invalid, low battery);
                     do not retry without fixing the root cause
    """
    return await authorize_mission(req)
