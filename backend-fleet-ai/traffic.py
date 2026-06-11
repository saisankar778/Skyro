"""
traffic.py — Air traffic conflict detection and obstacle alert handling.

Integrates CollisionEngine from collision.py for 3D R-tree trajectory checks.

Algorithm:
  1. Fetch current drone states from state_manager.
  2. Predict each drone's position N seconds ahead using its velocity.
  3. Compute pairwise great-circle distances of predicted positions.
  4. If distance < SAFE_THRESHOLD_M → flag as conflict.
  5. Suggest resolution: altitude separation or delayed launch.

For new trajectory registrations (from /assign-drone flow):
  - register_drone_trajectory() builds a TrajectorySegment and checks
    against the R-tree index.
  - On loiter required: emit drone_loiter_command WS event.
  - On altitude offset: return adjusted altitude to caller.

Endpoints:
    GET  /conflicts       — list all current predicted conflicts
    POST /obstacle-alert  — receive alert from drone, broadcast, and store
"""

from __future__ import annotations

import asyncio
import math
import os
import time
from typing import Dict, List, Optional, Tuple

import structlog
from fastapi import APIRouter

from collision import (
    PRIORITY_EXPRESS,
    PRIORITY_MEDICAL,
    PRIORITY_STANDARD,
    TrajectorySegment,
    get_collision_engine,
)
from models import (
    ConflictPair,
    ConflictsResponse,
    DroneState,
    ObstacleAlertRequest,
)

log = structlog.get_logger(__name__)
router = APIRouter(tags=["traffic"])

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
SAFE_THRESHOLD_M: float = float(os.getenv("SAFE_THRESHOLD_M", "20.0"))
PREDICT_SECONDS:  float = float(os.getenv("PREDICT_SECONDS",  "7.0"))

# Altitude separation to suggest when resolving legacy pairwise conflicts (metres)
ALT_SEP_M: float = 5.0

# Store recent obstacle alerts in memory (bounded ring buffer)
_MAX_ALERTS = 200
_OBSTACLE_ALERTS: List[dict] = []
_ALERTS_LOCK = asyncio.Lock()

# Active trajectory segments (maintained alongside CollisionEngine)
_active_segments: Dict[str, TrajectorySegment] = {}
_SEGMENTS_LOCK = asyncio.Lock()

# Order priority → collision priority
_ORDER_TO_COLLISION_PRIORITY = {5: PRIORITY_MEDICAL, 4: PRIORITY_EXPRESS}


# ---------------------------------------------------------------------------
# Priority mapping
# ---------------------------------------------------------------------------

def order_priority_to_collision(order_priority: int) -> int:
    """Map order priority (1–5) to collision priority constant."""
    return _ORDER_TO_COLLISION_PRIORITY.get(order_priority, PRIORITY_STANDARD)


# ---------------------------------------------------------------------------
# Geometry helpers
# ---------------------------------------------------------------------------

def _haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle distance in metres."""
    R = 6_371_000.0
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (
        math.sin(dlat / 2) ** 2
        + math.cos(math.radians(lat1))
        * math.cos(math.radians(lat2))
        * math.sin(dlon / 2) ** 2
    )
    return R * 2 * math.asin(math.sqrt(max(0.0, a)))


def _predict_position(state: DroneState, dt: float) -> Tuple[float, float, float]:
    """
    Linear prediction of lat/lon/alt using velocity components.
    velocity_x = m/s north, velocity_y = m/s east, velocity_z = m/s down.
    """
    METRES_PER_DEG_LAT = 111_320.0
    metres_per_deg_lon = 111_320.0 * math.cos(math.radians(state.lat))

    future_lat = state.lat + (state.velocity_x * dt) / METRES_PER_DEG_LAT
    future_lon = state.lon + (state.velocity_y * dt) / max(metres_per_deg_lon, 1.0)
    future_alt = state.alt - (state.velocity_z * dt)  # z is positive-down

    return future_lat, future_lon, future_alt


# ---------------------------------------------------------------------------
# Core conflict detection (O(n²) pairwise — for /conflicts endpoint)
# ---------------------------------------------------------------------------

def detect_conflicts(
    drone_states: Dict[str, DroneState],
    predict_s: float = PREDICT_SECONDS,
    threshold_m: float = SAFE_THRESHOLD_M,
) -> List[ConflictPair]:
    """
    Check all pairs of active drones for predicted conflicts.
    Only considers drones with status != 'IDLE' and status != 'OFFLINE'.
    """
    active: List[Tuple[str, DroneState]] = [
        (did, state)
        for did, state in drone_states.items()
        if state.status not in ("IDLE", "OFFLINE", "UNKNOWN", "COOLDOWN")
    ]

    conflicts: List[ConflictPair] = []
    n = len(active)

    for i in range(n):
        id_a, state_a = active[i]
        fut_lat_a, fut_lon_a, fut_alt_a = _predict_position(state_a, predict_s)

        for j in range(i + 1, n):
            id_b, state_b = active[j]
            fut_lat_b, fut_lon_b, fut_alt_b = _predict_position(state_b, predict_s)

            horiz_m = _haversine_m(fut_lat_a, fut_lon_a, fut_lat_b, fut_lon_b)
            vert_m  = abs(fut_alt_a - fut_alt_b)
            dist_3d = math.sqrt(horiz_m ** 2 + vert_m ** 2)

            if dist_3d < threshold_m:
                if vert_m < ALT_SEP_M:
                    resolution = (
                        f"altitude_separation: raise {id_a} by {ALT_SEP_M:.0f}m "
                        f"or delay launch of {id_b}"
                    )
                else:
                    resolution = f"delayed_launch: hold {id_b} for 10s"

                conflicts.append(
                    ConflictPair(
                        drone_a=id_a,
                        drone_b=id_b,
                        predicted_dist_m=round(dist_3d, 2),
                        resolution=resolution,
                    )
                )
                log.warning(
                    "conflict_predicted",
                    event="conflict_predicted",
                    service="fleet-ai",
                    drone_a=id_a,
                    drone_b=id_b,
                    dist_m=round(dist_3d, 1),
                    predict_s=predict_s,
                )

    return conflicts


# ---------------------------------------------------------------------------
# Trajectory registration (called from /assign-drone flow in main.py)
# ---------------------------------------------------------------------------

async def register_drone_trajectory(
    drone_id: str,
    start_lat: float,
    start_lon: float,
    start_alt: float,
    end_lat: float,
    end_lon: float,
    end_alt: float,
    order_priority: int = 1,
) -> Tuple[float, bool]:
    """
    Register a drone's planned trajectory in the collision engine.

    Returns (alt_offset_m, should_loiter):
      (0, False)   → no conflict, registered at original altitude
      (n, False)   → registered at end_alt + n metres to avoid conflict
      (0, True)    → loiter required; WS event emitted, caller waits

    When should_loiter=True, Fleet AI emits drone_loiter_command and
    the drone backend handles the MAVSDK hold. After LOITER_DURATION_S,
    the caller re-registers.
    """
    LOITER_DURATION_S = 8

    engine = get_collision_engine()
    coll_priority = order_priority_to_collision(order_priority)

    candidate = TrajectorySegment(
        drone_id=drone_id,
        start_lat=start_lat,
        start_lon=start_lon,
        start_alt=start_alt,
        end_lat=end_lat,
        end_lon=end_lon,
        end_alt=end_alt,
        priority=coll_priority,
        dispatched_at=time.time(),
    )

    async with _SEGMENTS_LOCK:
        all_active = list(_active_segments.values())

    alt_offset, should_loiter = engine.check_and_resolve(candidate, all_active)

    if should_loiter:
        log.warning(
            "trajectory_loiter_required",
            event="trajectory_loiter_required",
            service="fleet-ai",
            drone_id=drone_id,
        )
        # Emit loiter command — drone backend executes MAVSDK hold
        try:
            from main import fleet_ws_manager, _make_ws_event
            await fleet_ws_manager.broadcast_json(
                _make_ws_event(
                    "drone_loiter_command",
                    drone_id=drone_id,
                    data={"duration_seconds": LOITER_DURATION_S},
                )
            )
        except Exception as ws_exc:
            log.warning(
                "loiter_ws_emit_error",
                event="loiter_ws_emit_error",
                service="fleet-ai",
                drone_id=drone_id,
                error=str(ws_exc),
            )

        # Track loiter duration in Fleet AI, then emit resolved event
        async def _emit_resolved_after_loiter():
            await asyncio.sleep(LOITER_DURATION_S)
            try:
                from main import fleet_ws_manager, _make_ws_event
                await fleet_ws_manager.broadcast_json(
                    _make_ws_event(
                        "flight_conflict_resolved",
                        drone_id=drone_id,
                        data={"resolution_type": "loiter", "alt_offset_m": 0},
                    )
                )
            except Exception:
                pass

        asyncio.create_task(_emit_resolved_after_loiter())
        return (0.0, True)

    # Register at resolved altitude
    resolved_seg = TrajectorySegment(
        drone_id=drone_id,
        start_lat=start_lat,
        start_lon=start_lon,
        start_alt=start_alt + alt_offset,
        end_lat=end_lat,
        end_lon=end_lon,
        end_alt=end_alt + alt_offset,
        priority=coll_priority,
        dispatched_at=candidate.dispatched_at,
    )
    engine.register_trajectory(resolved_seg)
    async with _SEGMENTS_LOCK:
        _active_segments[drone_id] = resolved_seg

    if alt_offset > 0:
        try:
            from main import fleet_ws_manager, _make_ws_event
            await fleet_ws_manager.broadcast_json(
                _make_ws_event(
                    "flight_conflict_resolved",
                    drone_id=drone_id,
                    data={"resolution_type": "altitude_offset", "alt_offset_m": alt_offset},
                )
            )
        except Exception:
            pass

    return (alt_offset, False)


async def deregister_drone_trajectory(drone_id: str) -> None:
    """Remove a drone's trajectory from the collision engine."""
    engine = get_collision_engine()
    engine.deregister_trajectory(drone_id)
    async with _SEGMENTS_LOCK:
        _active_segments.pop(drone_id, None)


async def rebuild_collision_from_active() -> None:
    """Rebuild collision engine from drones currently IN_FLIGHT in state manager."""
    from state_manager import get_all_states
    states = await get_all_states()
    engine = get_collision_engine()
    engine.rebuild_from_active(
        {did: {"status": s.status, "lat": s.lat, "lon": s.lon, "alt": s.alt}
         for did, s in states.items()}
    )


# ---------------------------------------------------------------------------
# Obstacle alerts storage
# ---------------------------------------------------------------------------

async def store_obstacle_alert(alert: dict) -> None:
    async with _ALERTS_LOCK:
        _OBSTACLE_ALERTS.append(alert)
        if len(_OBSTACLE_ALERTS) > _MAX_ALERTS:
            _OBSTACLE_ALERTS.pop(0)


async def get_recent_alerts(limit: int = 20) -> List[dict]:
    async with _ALERTS_LOCK:
        return list(_OBSTACLE_ALERTS[-limit:])


# ---------------------------------------------------------------------------
# Router endpoints
# ---------------------------------------------------------------------------

@router.get(
    "/conflicts",
    summary="Get active predicted air traffic conflicts",
    response_model=ConflictsResponse,
)
async def get_conflicts() -> ConflictsResponse:
    """
    Returns all pairs of drones predicted to come within SAFE_THRESHOLD_M
    of each other in the next PREDICT_SECONDS seconds.
    """
    from state_manager import get_all_states
    states = await get_all_states()
    conflicts = detect_conflicts(states)
    return ConflictsResponse(conflicts=conflicts, safe=len(conflicts) == 0)


@router.post(
    "/obstacle-alert",
    summary="Receive an obstacle detection alert from a drone",
)
async def obstacle_alert(req: ObstacleAlertRequest) -> dict:
    """
    Store obstacle alert and broadcast to all Fleet AI WS subscribers.
    """
    alert_doc = {
        "timestamp": time.time(),
        "droneId":   req.droneId,
        "lat":       req.lat,
        "lon":       req.lon,
        "alt":       req.alt,
        "severity":  req.severity,
    }
    await store_obstacle_alert(alert_doc)

    log.warning(
        "obstacle_alert_received",
        event="obstacle_alert_received",
        service="fleet-ai",
        drone_id=req.droneId,
        lat=req.lat,
        lon=req.lon,
        alt=req.alt,
        severity=req.severity,
    )

    try:
        from main import fleet_ws_manager, _make_ws_event
        await fleet_ws_manager.broadcast_json(
            _make_ws_event("obstacle_alert", drone_id=req.droneId, data=alert_doc)
        )
    except Exception:
        pass

    return {"status": "alert_received", "droneId": req.droneId, "severity": req.severity}
