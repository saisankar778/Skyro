"""
backend-fleet-ai/landing.py

Landing Zone (Delivery Block) and Home Location reservation system.

All locks now use Redis SET NX for distributed, race-condition-safe locking:

  Delivery zone locks — Redis SET NX key=delivery_lock:{zone} EX 180s
  Home pad locks      — Redis SET NX key=home_pad_lock:{pad} EX 600s (active mission)
                        Redis SET key=home_pad_lock:{pad}          (persistent, no TTL)

Boot-time pad reconstruction reads PostgreSQL home_location_reservations
and restores persistent Redis locks for all drones that were parked at
a home pad at the time of shutdown.

Endpoints:
  POST /reserve-landing            — acquire delivery zone Redis lock
  POST /landing/confirm            — release delivery zone Redis lock
  GET  /zone-status                — list delivery zones (synced from Redis)
  POST /reserve-home-location      — find and lock a free HOME pad
  POST /release-home-location      — release home pad lock
  GET  /home-status                — list home pad states from Redis
  POST /on-home-landing            — validate landing telemetry, set persistent lock
"""

from __future__ import annotations

import asyncio
import os
import time
import structlog
from typing import Dict, List, Optional

import asyncpg
import httpx
from fastapi import APIRouter, HTTPException

from models import (
    HomeLandingRequest,
    HomeLocationRequest,
    HomeLocationResponse,
    LandingConfirmRequest,
    LandingZoneStatus,
    ReserveLandingRequest,
    ReleaseHomeRequest,
)

log = structlog.get_logger(__name__)
router = APIRouter()

ORDERS_API_BASE: str = os.getenv(
    "ORDERS_API_BASE",
    "https://fff8-2401-4900-cbd5-7c0d-d549-241c-a989-4b7a.ngrok-free.app",
)

# PostgreSQL direct connection (for boot reconstruction only)
DATABASE_URL: str = os.getenv("DATABASE_URL", "")

# Redis lock TTLs
_DELIVERY_LOCK_TTL_S: int = 180   # delivery zone lock
_HOME_LOCK_MISSION_TTL_S: int = 600  # home pad lock during active mission
_DELIVERY_LOCK_POLL_INTERVAL_S: float = 5.0
_DELIVERY_LOCK_MAX_WAIT_S: float = 120.0


# ─────────────────────────────────────────────────────────────────────────────
# Redis helpers
# ─────────────────────────────────────────────────────────────────────────────

async def _get_redis():
    from redis_client import get_redis
    return await get_redis()


async def _broadcast(event: dict) -> None:
    """Best-effort WS broadcast — never raises."""
    try:
        from main import fleet_ws_manager
        await fleet_ws_manager.broadcast_json(event)
    except Exception:
        pass


def _make_event(event_type: str, drone_id: Optional[str] = None, **data) -> dict:
    from main import _make_ws_event
    return _make_ws_event(event_type, drone_id=drone_id, data=data)


# ─────────────────────────────────────────────────────────────────────────────
# DELIVERY ZONE — Redis SET NX locking
# ─────────────────────────────────────────────────────────────────────────────

def _normalize_zone(name: str) -> str:
    if name.upper().startswith("HOME"):
        return name.strip()
    return name.replace("_", " ").replace("and", "&").replace("  ", " ").strip().title()

async def acquire_delivery_lock(station_id: str, drone_id: str) -> bool:
    """
    Try to acquire a Redis SET NX lock for a delivery zone.

    - Immediately tries SET NX with EX 180.
    - On failure, emits landing_clearance_denied and polls every 5s up to 120s.
    - On timeout, emits landing_aborted and returns False.
    """
    station_id = _normalize_zone(station_id)
    key = f"delivery_lock:{station_id}"
    r = await _get_redis()

    # Re-entrancy check: if the lock is already held by this drone, allow it and refresh lease
    try:
        current = await r.get(key)
        if current == drone_id:
            await r.expire(key, _DELIVERY_LOCK_TTL_S)
            log.info(
                "delivery_lock_reacquired",
                event="delivery_lock_reacquired",
                service="fleet-ai",
                drone_id=drone_id,
                zone=station_id,
            )
            return True
    except Exception as exc:
        log.warning(
            "delivery_lock_read_error",
            event="delivery_lock_read_error",
            service="fleet-ai",
            zone=station_id,
            error=str(exc),
        )

    # First attempt
    acquired = await r.set(key, drone_id, nx=True, ex=_DELIVERY_LOCK_TTL_S)
    if acquired:
        log.info(
            "delivery_lock_acquired",
            event="delivery_lock_acquired",
            service="fleet-ai",
            drone_id=drone_id,
            zone=station_id,
        )
        return True

    # Lock taken — emit WS event and start polling
    await _broadcast(_make_event(
        "landing_clearance_denied",
        drone_id=drone_id,
        zone=station_id,
        wait_started_at=time.time(),
    ))
    log.info(
        "delivery_lock_waiting",
        event="delivery_lock_waiting",
        service="fleet-ai",
        drone_id=drone_id,
        zone=station_id,
    )

    deadline = time.time() + _DELIVERY_LOCK_MAX_WAIT_S
    while time.time() < deadline:
        await asyncio.sleep(_DELIVERY_LOCK_POLL_INTERVAL_S)
        acquired = await r.set(key, drone_id, nx=True, ex=_DELIVERY_LOCK_TTL_S)
        if acquired:
            log.info(
                "delivery_lock_acquired_after_wait",
                event="delivery_lock_acquired_after_wait",
                service="fleet-ai",
                drone_id=drone_id,
                zone=station_id,
            )
            return True

    # Timeout
    await _broadcast(_make_event(
        "landing_aborted",
        drone_id=drone_id,
        zone=station_id,
    ))
    log.warning(
        "delivery_lock_timeout",
        event="delivery_lock_timeout",
        service="fleet-ai",
        drone_id=drone_id,
        zone=station_id,
        wait_s=_DELIVERY_LOCK_MAX_WAIT_S,
    )
    return False


async def release_delivery_lock(station_id: str) -> None:
    """Release a delivery zone Redis lock (DEL key)."""
    station_id = _normalize_zone(station_id)
    key = f"delivery_lock:{station_id}"
    try:
        r = await _get_redis()
        await r.delete(key)
        log.info(
            "delivery_lock_released",
            event="delivery_lock_released",
            service="fleet-ai",
            zone=station_id,
        )
    except Exception as exc:
        log.warning(
            "delivery_lock_release_error",
            event="delivery_lock_release_error",
            service="fleet-ai",
            zone=station_id,
            error=str(exc),
        )


# ─────────────────────────────────────────────────────────────────────────────
# HOME PAD — Redis locking
# ─────────────────────────────────────────────────────────────────────────────

async def acquire_home_pad_lock(pad_id: str, drone_id: str, persistent: bool = False) -> bool:
    """
    Lock a home pad for a drone.

    persistent=True  → SET key value  (no TTL — drone is parked at home)
    persistent=False → SET NX key value EX 600  (active mission hold)

    Returns True if lock was set, False if key already existed (non-persistent only).
    """
    key = f"home_pad_lock:{pad_id}"
    r = await _get_redis()

    if persistent:
        await r.set(key, drone_id)  # overwrite any existing TTL
        log.info(
            "home_pad_locked_persistent",
            event="home_pad_locked_persistent",
            service="fleet-ai",
            drone_id=drone_id,
            pad_id=pad_id,
        )
        return True
    else:
        # Re-entrancy check: if home pad is already locked by this drone, allow it
        try:
            current = await r.get(key)
            if current == drone_id:
                await r.expire(key, _HOME_LOCK_MISSION_TTL_S)
                log.info(
                    "home_pad_lock_reacquired",
                    event="home_pad_lock_reacquired",
                    service="fleet-ai",
                    drone_id=drone_id,
                    pad_id=pad_id,
                    ttl_s=_HOME_LOCK_MISSION_TTL_S,
                )
                return True
        except Exception as exc:
            log.warning(
                "home_pad_lock_read_error",
                event="home_pad_lock_read_error",
                service="fleet-ai",
                pad_id=pad_id,
                error=str(exc),
            )

        acquired = await r.set(key, drone_id, nx=True, ex=_HOME_LOCK_MISSION_TTL_S)
        if acquired:
            log.info(
                "home_pad_locked_mission",
                event="home_pad_locked_mission",
                service="fleet-ai",
                drone_id=drone_id,
                pad_id=pad_id,
                ttl_s=_HOME_LOCK_MISSION_TTL_S,
            )
        return bool(acquired)


async def release_home_pad_lock(pad_id: str) -> None:
    """Release a home pad lock (DEL key)."""
    key = f"home_pad_lock:{pad_id}"
    try:
        r = await _get_redis()
        await r.delete(key)
        log.info(
            "home_pad_lock_released",
            event="home_pad_lock_released",
            service="fleet-ai",
            pad_id=pad_id,
        )
    except Exception as exc:
        log.warning(
            "home_pad_lock_release_error",
            event="home_pad_lock_release_error",
            service="fleet-ai",
            pad_id=pad_id,
            error=str(exc),
        )


async def get_home_pad_occupant(pad_id: str) -> Optional[str]:
    """Return the drone_id holding pad_id, or None if free."""
    try:
        r = await _get_redis()
        return await r.get(f"home_pad_lock:{pad_id}")
    except Exception as exc:
        log.warning(
            "home_pad_get_occupant_error",
            event="home_pad_get_occupant_error",
            service="fleet-ai",
            pad_id=pad_id,
            error=str(exc),
        )
        return None


# ─────────────────────────────────────────────────────────────────────────────
# BOOT RECONSTRUCTION — restore home pad locks from PostgreSQL
# ─────────────────────────────────────────────────────────────────────────────

async def boot_pad_reconstruction() -> int:
    """
    Query PostgreSQL home_location_reservations JOIN locations.
    For each reserved row, restore:
      - Redis SET home_pad_lock:{location_name} {drone_id} (no TTL)
      - Redis SET drone_state:{drone_id} IDLE (no TTL)

    Returns: count of pads restored.
    Raises: RuntimeError on DB failure (caller should retry every 10s).
    """
    if not DATABASE_URL or not DATABASE_URL.startswith("postgresql"):
        log.warning(
            "boot_reconstruction_skipped",
            event="boot_reconstruction_skipped",
            service="fleet-ai",
            reason="DATABASE_URL not set or not PostgreSQL",
        )
        return 0

    start_t = time.monotonic()
    count = 0

    try:
        import ssl
        import re as _re

        _url = DATABASE_URL.replace("postgresql+asyncpg://", "").replace("postgresql://", "")
        _match = _re.match(r"([^:]+):([^@]+)@([^:/]+):?(\d+)?/([^?]+)", _url)
        if not _match:
            raise RuntimeError(f"Cannot parse DATABASE_URL: {DATABASE_URL}")

        pg_user, pg_pass, pg_host, pg_port, pg_db = _match.groups()
        pg_port = int(pg_port or 5432)

        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        use_ssl = ctx if "amazonaws.com" in pg_host else False

        conn = await asyncpg.connect(
            host=pg_host, port=pg_port, user=pg_user, password=pg_pass,
            database=pg_db, ssl=use_ssl, timeout=10.0,
        )

        try:
            rows = await conn.fetch(
                """
                SELECT l.name AS pad_name, hlr.reserved_by_drone AS drone_id
                FROM home_location_reservations hlr
                JOIN locations l ON l.id = hlr.location_id
                WHERE hlr.is_reserved = true
                  AND hlr.reserved_by_drone IS NOT NULL
                  AND l.type = 'HOME'
                """
            )
        finally:
            await conn.close()

        r = await _get_redis()

        # Reset/clear existing locks and drone states in Redis on restart
        try:
            old_delivery_keys = await r.keys("delivery_lock:*")
            old_pad_keys = await r.keys("home_pad_lock:*")
            old_state_keys = await r.keys("drone_state:*")
            clear_keys = old_delivery_keys + old_pad_keys + old_state_keys
            if clear_keys:
                await r.delete(*clear_keys)
                log.info(
                    "startup_keys_cleared",
                    event="startup_keys_cleared",
                    service="fleet-ai",
                    count=len(clear_keys),
                )
        except Exception as exc:
            log.warning(
                "startup_keys_clear_error",
                event="startup_keys_clear_error",
                service="fleet-ai",
                error=str(exc),
            )

        # Check physical drone locations from drone backend
        physical_locks = {}
        try:
            from state_manager import DRONE_BACKEND_URL
            from location_cache import get_home_locations
            import math

            home_locs = await get_home_locations()
            if home_locs:
                async with httpx.AsyncClient(timeout=3.0) as client:
                    resp = await client.get(
                        f"{DRONE_BACKEND_URL}/api/drones/status",
                        headers={"ngrok-skip-browser-warning": "true"},
                    )
                    if resp.status_code == 200:
                        drones_data = resp.json().get("drones", {})
                        for drone_id, d_info in drones_data.items():
                            d_lat = d_info.get("lat")
                            d_lon = d_info.get("lon")
                            d_status = d_info.get("status", "")
                            # Only check stationary/parked drones (not in flight)
                            if (
                                d_lat is not None
                                and d_lon is not None
                                and d_status not in ("IN_FLIGHT", "RETURNING_HOME", "LANDING")
                            ):
                                for loc in home_locs:
                                    # Haversine distance in meters
                                    lat1, lon1 = d_lat, d_lon
                                    lat2, lon2 = loc["lat"], loc["lon"]
                                    dlat = math.radians(lat2 - lat1)
                                    dlon = math.radians(lon2 - lon1)
                                    a = (
                                        math.sin(dlat / 2) ** 2
                                        + math.cos(math.radians(lat1))
                                        * math.cos(math.radians(lat2))
                                        * math.sin(dlon / 2) ** 2
                                    )
                                    dist_m = 6371000.0 * 2 * math.asin(math.sqrt(max(0.0, a)))
                                    if dist_m < 5.0:  # within 5 meters
                                        physical_locks[loc["name"]] = drone_id
                                        log.info(
                                            "boot_physical_presence_detected",
                                            event="boot_physical_presence_detected",
                                            service="fleet-ai",
                                            drone_id=drone_id,
                                            pad_id=loc["name"],
                                            distance_m=round(dist_m, 2),
                                            status=d_status,
                                        )
                                        break
        except Exception as exc:
            log.warning(
                "boot_physical_check_failed",
                event="boot_physical_check_failed",
                service="fleet-ai",
                error=str(exc),
            )

        locks_to_restore = {}
        # 1. Restore reservations from DB
        for row in rows:
            locks_to_restore[row["pad_name"]] = row["drone_id"]

        # 2. Overlay physical locks (takes precedence since the drone is physically sitting on the pad)
        for pad_name, drone_id in physical_locks.items():
            locks_to_restore[pad_name] = drone_id

        pipe = r.pipeline()
        for pad_name, drone_id in locks_to_restore.items():
            pipe.set(f"home_pad_lock:{pad_name}", drone_id)  # no TTL
            pipe.set(f"drone_state:{drone_id}", "IDLE")       # no TTL
            log.info(
                "boot_pad_restored",
                event="boot_pad_restored",
                service="fleet-ai",
                pad_id=pad_name,
                drone_id=drone_id,
            )
            count += 1
        await pipe.execute()

        elapsed_ms = int((time.monotonic() - start_t) * 1000)
        log.info(
            "boot_pad_reconstruction_complete",
            event="boot_pad_reconstruction_complete",
            service="fleet-ai",
            pads_locked=count,
            duration_ms=elapsed_ms,
        )

        # Emit WS event (non-blocking, best-effort)
        asyncio.create_task(_broadcast(_make_event(
            "boot_pad_reconstruction_complete",
            data={"pads_locked": count, "duration_ms": elapsed_ms},
        )))

        return count

    except Exception as exc:
        raise RuntimeError(f"boot_pad_reconstruction failed: {exc}") from exc


# ─────────────────────────────────────────────────────────────────────────────
# POST-LANDING CONFIRMATION
# ─────────────────────────────────────────────────────────────────────────────

async def on_drone_home_landing_confirmed(
    drone_id: str, pad_id: str, velocity: float, altitude: float
) -> None:
    """
    Called by drone backend after drone lands at home pad.
    Validates telemetry, then sets a persistent Redis lock.

    velocity < 0.2 m/s and altitude < 0.3 m required for confirmation.
    """
    if velocity >= 0.2 or altitude >= 0.3:
        log.warning(
            "home_landing_telemetry_invalid",
            event="home_landing_telemetry_invalid",
            service="fleet-ai",
            drone_id=drone_id,
            pad_id=pad_id,
            velocity=velocity,
            altitude=altitude,
        )
        raise ValueError(
            f"Landing telemetry out of bounds: velocity={velocity:.3f} m/s, altitude={altitude:.3f} m. "
            "Expected velocity < 0.2 and altitude < 0.3."
        )

    # Persistent lock (no TTL)
    await acquire_home_pad_lock(pad_id, drone_id, persistent=True)

    # Record landing timestamp and start cooldown tracking
    now = time.time()
    try:
        r = await _get_redis()
        pipe = r.pipeline()
        pipe.set(f"last_landed_at:{drone_id}", str(now))
        pipe.hset(f"telemetry:{drone_id}", "last_landed_at", str(now))
        await pipe.execute()
    except Exception as exc:
        log.warning(
            "home_landing_redis_error",
            event="home_landing_redis_error",
            service="fleet-ai",
            drone_id=drone_id,
            error=str(exc),
        )

    cooldown_until = now + 60
    await _broadcast(_make_event(
        "drone_cooldown_started",
        drone_id=drone_id,
        cooldown_until=cooldown_until,
    ))

    log.info(
        "home_landing_confirmed",
        event="home_landing_confirmed",
        service="fleet-ai",
        drone_id=drone_id,
        pad_id=pad_id,
        velocity=velocity,
        altitude=altitude,
    )


# ─────────────────────────────────────────────────────────────────────────────
# STARTUP HOOK (load and sync home location data to Redis)
# ─────────────────────────────────────────────────────────────────────────────

async def init_home_locations() -> None:
    """
    Pre-warm home location data from location_cache on startup.
    Boot reconstruction (boot_pad_reconstruction) is called separately.
    """
    from location_cache import get_home_locations
    try:
        home_locs = await get_home_locations()
        log.info(
            "home_locations_loaded",
            event="home_locations_loaded",
            service="fleet-ai",
            count=len(home_locs),
        )
    except Exception as exc:
        log.warning(
            "home_locations_load_failed",
            event="home_locations_load_failed",
            service="fleet-ai",
            error=str(exc),
        )


# ─────────────────────────────────────────────────────────────────────────────
# BACKGROUND: stale delivery zone cleaner (Redis-based)
# ─────────────────────────────────────────────────────────────────────────────

async def stale_reservation_cleaner() -> None:
    """
    Background task. Logs all currently active delivery zone Redis locks every 60s.
    Actual TTL enforcement is handled by Redis expiry (EX 180s).
    """
    while True:
        await asyncio.sleep(60)
        try:
            r = await _get_redis()
            keys = await r.keys("delivery_lock:*")
            if keys:
                for key in keys:
                    occupant = await r.get(key)
                    ttl = await r.ttl(key)
                    log.debug(
                        "delivery_lock_active",
                        event="delivery_lock_active",
                        service="fleet-ai",
                        zone=key.replace("delivery_lock:", ""),
                        occupant=occupant,
                        ttl_remaining_s=ttl,
                    )
        except Exception as exc:
            log.warning(
                "stale_cleaner_error",
                event="stale_cleaner_error",
                service="fleet-ai",
                error=str(exc),
            )


# ─────────────────────────────────────────────────────────────────────────────
# DELIVERY ZONE ENDPOINTS
# ─────────────────────────────────────────────────────────────────────────────

@router.post("/reserve-landing")
async def reserve_landing(req: ReserveLandingRequest):
    """
    Lock a delivery zone using Redis SET NX (EX 180s).
    Polls for up to 120s if zone is busy. Returns 503 on timeout.
    """
    req.zone = _normalize_zone(req.zone)
    acquired = await acquire_delivery_lock(req.zone, req.droneId)
    if not acquired:
        raise HTTPException(
            status_code=503,
            detail=(
                f"Delivery zone '{req.zone}' is occupied and did not clear within "
                f"{int(_DELIVERY_LOCK_MAX_WAIT_S)}s. Order should be re-queued."
            ),
        )
    return {"zone": req.zone, "reserved": True, "droneId": req.droneId}


@router.post("/landing/confirm")
async def confirm_landing(req: LandingConfirmRequest):
    """Confirm landing and release the delivery zone Redis lock."""
    req.zone = _normalize_zone(req.zone)
    if req.landing_mode == "VISION":
        log.info(
            "vision_landing_confirm",
            event="vision_landing_confirm",
            service="fleet-ai",
            drone_id=req.droneId,
            zone=req.zone,
            offset_x=req.offset_x,
            offset_y=req.offset_y,
        )
    else:
        log.info(
            "gps_landing_confirm",
            event="gps_landing_confirm",
            service="fleet-ai",
            drone_id=req.droneId,
            zone=req.zone,
        )

    await release_delivery_lock(req.zone)

    return {
        "zone":         req.zone,
        "occupied":     False,
        "droneId":      req.droneId,
        "landing_mode": req.landing_mode,
    }


@router.get("/zone-status")
async def get_zone_status():
    """Current reservation status of all delivery zones (reads from Redis)."""
    try:
        r = await _get_redis()
        keys = await r.keys("delivery_lock:*")
        occupied_zones: Dict[str, str] = {}
        for key in keys:
            occupant = await r.get(key)
            zone_name = key.replace("delivery_lock:", "")
            occupied_zones[zone_name] = occupant or ""
    except Exception as exc:
        log.warning(
            "zone_status_redis_error",
            event="zone_status_redis_error",
            service="fleet-ai",
            error=str(exc),
        )
        occupied_zones = {}

    # Load all known delivery zone names from location cache to show free zones too
    from location_cache import get_delivery_locations
    try:
        delivery_locs = await get_delivery_locations()
    except Exception:
        delivery_locs = []

    all_zones = {loc["name"] for loc in delivery_locs}
    all_zones.update(occupied_zones.keys())

    return [
        LandingZoneStatus(
            zone=zone,
            occupied=zone in occupied_zones,
            drone=occupied_zones.get(zone),
        )
        for zone in sorted(all_zones)
    ]


# ─────────────────────────────────────────────────────────────────────────────
# HOME LOCATION ENDPOINTS
# ─────────────────────────────────────────────────────────────────────────────

@router.post("/reserve-home-location", response_model=HomeLocationResponse)
async def reserve_home_location(req: HomeLocationRequest):
    """
    Find the first free HOME pad and lock it for the requesting drone.
    Returns 503 if all pads are occupied.
    """
    from location_cache import get_home_locations
    home_locs = await get_home_locations()

    if not home_locs:
        raise HTTPException(status_code=503, detail="No HOME locations configured in the database.")

    r = await _get_redis()

    # Re-entrancy check: if this drone already holds a lock on a pad, reuse it!
    for loc in home_locs:
        occupant = await r.get(f"home_pad_lock:{loc['name']}")
        if occupant == req.droneId:
            await acquire_home_pad_lock(loc["name"], req.droneId, persistent=False)
            log.info(
                "home_pad_reserved_reentrant",
                event="home_pad_reserved_reentrant",
                service="fleet-ai",
                drone_id=req.droneId,
                pad_id=loc["name"],
            )
            return HomeLocationResponse(
                zone=loc["name"],
                lat=loc["lat"],
                lon=loc["lon"],
                reserved=True,
            )

    # Find first free pad
    free_slot = None
    for loc in home_locs:
        occupant = await r.get(f"home_pad_lock:{loc['name']}")
        if occupant is None:
            free_slot = loc
            break

    if free_slot is None:
        raise HTTPException(
            status_code=503,
            detail="All home pads are currently reserved. Retry shortly.",
        )

    # Lock with mission TTL (drone is en route — not yet confirmed landed)
    acquired = await acquire_home_pad_lock(free_slot["name"], req.droneId, persistent=False)
    if not acquired:
        # Race condition: another drone just grabbed it — retry recursively would be cleaner
        raise HTTPException(
            status_code=503,
            detail=f"Home pad '{free_slot['name']}' was taken by another drone. Retry.",
        )

    return HomeLocationResponse(
        zone=free_slot["name"],
        lat=free_slot["lat"],
        lon=free_slot["lon"],
        reserved=True,
    )


@router.post("/release-home-location")
async def release_home_location(req: ReleaseHomeRequest):
    """Release a home pad lock after the drone has landed."""
    # Validate ownership
    occupant = await get_home_pad_occupant(req.zone)
    if occupant and occupant != req.droneId:
        raise HTTPException(
            status_code=403,
            detail=f"Pad '{req.zone}' is held by '{occupant}', not '{req.droneId}'.",
        )
    await release_home_pad_lock(req.zone)
    return {"zone": req.zone, "reserved": False, "droneId": req.droneId}


@router.get("/home-status")
async def get_home_status():
    """Current occupancy of all home landing pads (reads from Redis)."""
    from location_cache import get_home_locations
    try:
        home_locs = await get_home_locations()
    except Exception as exc:
        log.warning(
            "home_status_location_error",
            event="home_status_location_error",
            service="fleet-ai",
            error=str(exc),
        )
        home_locs = []

    result = []
    free_count = 0
    for loc in home_locs:
        occupant = await get_home_pad_occupant(loc["name"])
        reserved = occupant is not None
        if not reserved:
            free_count += 1
        result.append({
            "name":     loc["name"],
            "lat":      loc["lat"],
            "lon":      loc["lon"],
            "reserved": reserved,
            "drone":    occupant,
        })

    return {
        "home_locations": result,
        "free_count": free_count,
        "total": len(result),
    }


# ─────────────────────────────────────────────────────────────────────────────
# POST-LANDING CONFIRMATION ENDPOINT
# ─────────────────────────────────────────────────────────────────────────────

@router.post("/on-home-landing")
async def on_home_landing(req: HomeLandingRequest):
    """
    Called by drone backend after confirming drone is stationary at home pad.
    Validates telemetry and sets a persistent Redis lock.
    """
    try:
        await on_drone_home_landing_confirmed(
            drone_id=req.droneId,
            pad_id=req.pad_id,
            velocity=req.velocity,
            altitude=req.altitude,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    return {"confirmed": True, "droneId": req.droneId, "pad_id": req.pad_id}
