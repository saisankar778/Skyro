"""
state_manager.py — Real-time in-memory fleet state.

Maintains a live snapshot of every drone by subscribing to the Drone
Backend's WebSocket (/ws). Falls back to polling /api/drones/status
if the WebSocket is unavailable.

Design goals:
  - Thread-safe reads (asyncio.Lock) so scheduler/traffic/auth can
    call get_all_states() without race conditions.
  - Reconnects automatically on WS disconnect (exponential back-off).
  - Scales to 50–100 drones: dict lookup is O(1).
  - Writes each telemetry update to Redis hash `telemetry:{drone_id}` (TTL 60s).
"""

from __future__ import annotations

import asyncio
import json
import os
import time
from typing import Dict, Optional

import httpx
import structlog
import websockets
from websockets.exceptions import ConnectionClosedError, WebSocketException

from models import DroneState

log = structlog.get_logger(__name__)

# ---------------------------------------------------------------------------
# Config (overridable via environment)
# ---------------------------------------------------------------------------
DRONE_BACKEND_URL: str = os.getenv("DRONE_BACKEND_URL", "https://6deb-115-241-193-70.ngrok-free.app")
DRONE_BACKEND_WS:  str = os.getenv("DRONE_BACKEND_WS",  "wss://6deb-115-241-193-70.ngrok-free.app/ws")

# How long to consider a drone "OFFLINE" if we haven't heard from it (seconds)
STALE_THRESHOLD_S: float = 30.0

# Redis telemetry key TTL (seconds)
_REDIS_TELEMETRY_TTL: int = 60

# ---------------------------------------------------------------------------
# Internal state
# ---------------------------------------------------------------------------
_DRONE_STATES: Dict[str, DroneState] = {}
_LAST_SEEN:    Dict[str, float]       = {}  # drone_id -> epoch seconds
_LOCK = asyncio.Lock()


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

async def get_all_states() -> Dict[str, DroneState]:
    """Return a snapshot of all known drone states."""
    async with _LOCK:
        _mark_stale_offline()
        return dict(_DRONE_STATES)


async def get_state(drone_id: str) -> Optional[DroneState]:
    """Return state for a single drone, or None if unknown. Merges Redis telemetry extras."""
    async with _LOCK:
        state = _DRONE_STATES.get(drone_id)

    if state is None:
        return None

    # Merge extra fields from Redis (wind_speed_ms, signal_quality_percent, last_landed_at)
    redis_extra = await get_telemetry_from_redis(drone_id)
    if redis_extra:
        updates: dict = {}
        for field_name in ("wind_speed_ms", "signal_quality_percent", "last_landed_at"):
            if field_name in redis_extra and redis_extra[field_name] is not None:
                try:
                    updates[field_name] = float(redis_extra[field_name])
                except (ValueError, TypeError):
                    pass
        if updates:
            state = state.copy(update=updates)

    return state


async def update_state(drone_id: str, data: dict) -> DroneState:
    """
    Merge a raw telemetry dict into the state for drone_id.
    Also writes all fields to Redis hash `telemetry:{drone_id}` with TTL 60s.
    """
    async with _LOCK:
        existing = _DRONE_STATES.get(drone_id, DroneState(drone_id=drone_id))

        # Map drone backend field names → DroneState fields
        merged = existing.dict()
        merged["drone_id"] = drone_id
        merged["droneId"] = drone_id

        field_map = {
            "lat":       ["lat", "latitude"],
            "lon":       ["lon", "longitude"],
            "alt":       ["alt", "altitude"],
            "battery":   ["battery"],
            "status":    ["status"],
            "mode":      ["mode"],
            "armed":     ["armed"],
            "velocity_x":["velocity_x", "vx"],
            "velocity_y":["velocity_y", "vy"],
            "velocity_z":["velocity_z", "vz"],
            "historical_deliveries":["historical_deliveries", "historicalDeliveries"],
            "wind_speed_ms":         ["wind_speed_ms", "wind_speed"],
            "signal_quality_percent":["signal_quality_percent", "signal_quality"],
            "last_landed_at":        ["last_landed_at"],
            "deliveries_today":      ["deliveries_today"],
            "flight_minutes_today":  ["flight_minutes_today"],
            "cooldown_until":        ["cooldown_until"],
        }
        for state_field, raw_keys in field_map.items():
            for rk in raw_keys:
                if rk in data:
                    merged[state_field] = data[rk]
                    break

        # Handle nested location dict from drone backend
        if "location" in data and isinstance(data["location"], dict):
            loc = data["location"]
            merged["lat"] = loc.get("lat", merged["lat"])
            merged["lon"] = loc.get("lon", merged["lon"])
            merged["alt"] = loc.get("alt", merged["alt"])

        state = DroneState(**merged)
        _DRONE_STATES[drone_id] = state
        _LAST_SEEN[drone_id] = time.monotonic()

    # Write telemetry to Redis (outside lock to avoid blocking)
    await _write_telemetry_to_redis(drone_id, state)
    return state


async def _write_telemetry_to_redis(drone_id: str, state: DroneState) -> None:
    """Write all state fields to Redis hash `telemetry:{drone_id}` (TTL 60s)."""
    try:
        from redis_client import get_redis
        r = await get_redis()
        key = f"telemetry:{drone_id}"
        payload = {
            "lat":                   str(state.lat),
            "lon":                   str(state.lon),
            "alt":                   str(state.alt),
            "battery":               str(state.battery),
            "status":                state.status,
            "mode":                  state.mode,
            "armed":                 str(state.armed),
            "velocity_x":            str(state.velocity_x),
            "velocity_y":            str(state.velocity_y),
            "velocity_z":            str(state.velocity_z),
            "wind_speed_ms":         str(state.wind_speed_ms),
            "signal_quality_percent":str(state.signal_quality_percent),
            "deliveries_today":      str(state.deliveries_today),
            "flight_minutes_today":  str(state.flight_minutes_today),
            "last_seen":             str(time.time()),
        }
        if state.last_landed_at is not None:
            payload["last_landed_at"] = str(state.last_landed_at)
        if state.cooldown_until is not None:
            payload["cooldown_until"] = str(state.cooldown_until)

        pipe = r.pipeline()
        pipe.hset(key, mapping=payload)
        pipe.expire(key, _REDIS_TELEMETRY_TTL)
        await pipe.execute()
    except Exception as exc:
        log.warning(
            "telemetry_redis_write_error",
            event="telemetry_redis_write_error",
            service="fleet-ai",
            drone_id=drone_id,
            error=str(exc),
        )


async def get_telemetry_from_redis(drone_id: str) -> dict:
    """
    Read Redis hash `telemetry:{drone_id}`.
    Returns empty dict if key missing or Redis unavailable (never raises).
    """
    try:
        from redis_client import get_redis
        r = await get_redis()
        result = await r.hgetall(f"telemetry:{drone_id}")
        return result or {}
    except Exception as exc:
        log.warning(
            "telemetry_redis_read_error",
            event="telemetry_redis_read_error",
            service="fleet-ai",
            drone_id=drone_id,
            error=str(exc),
        )
        return {}


def _mark_stale_offline() -> None:
    """
    Mark drones as OFFLINE if no update received within STALE_THRESHOLD_S.
    Must be called while holding _LOCK.
    """
    now = time.monotonic()
    for drone_id, last in _LAST_SEEN.items():
        if (now - last) > STALE_THRESHOLD_S:
            if drone_id in _DRONE_STATES:
                state = _DRONE_STATES[drone_id]
                if state.status != "OFFLINE":
                    _DRONE_STATES[drone_id] = state.copy(
                        update={"status": "OFFLINE", "armed": False}
                    )


# ---------------------------------------------------------------------------
# Background sync: WebSocket subscriber
# ---------------------------------------------------------------------------

async def start_background_sync() -> None:
    """
    Entry-point called from FastAPI startup.
    Spawns the WS subscriber as a background task.
    """
    asyncio.create_task(_ws_reconnect_loop(), name="fleet_ws_sync")
    log.info(
        "fleet_ws_sync_started",
        event="fleet_ws_sync_started",
        service="fleet-ai",
    )


async def _ws_reconnect_loop() -> None:
    """Reconnects to the drone backend WS with exponential back-off."""
    delay = 2.0
    max_delay = 30.0

    while True:
        try:
            log.info(
                "ws_connecting",
                event="ws_connecting",
                service="fleet-ai",
                url=DRONE_BACKEND_WS,
            )
            async with websockets.connect(
                DRONE_BACKEND_WS,
                ping_interval=20,
                ping_timeout=20,
                open_timeout=10,
                additional_headers={"ngrok-skip-browser-warning": "true"},
            ) as ws:
                delay = 2.0  # reset back-off on successful connect
                log.info(
                    "ws_connected",
                    event="ws_connected",
                    service="fleet-ai",
                    url=DRONE_BACKEND_WS,
                )
                await _ws_listen(ws)

        except (ConnectionClosedError, WebSocketException, OSError) as exc:
            log.warning(
                "ws_disconnected",
                event="ws_disconnected",
                service="fleet-ai",
                error=str(exc),
                retry_in_s=delay,
            )
        except Exception as exc:
            log.error(
                "ws_unexpected_error",
                event="ws_unexpected_error",
                service="fleet-ai",
                error=str(exc),
                retry_in_s=delay,
            )

        await asyncio.sleep(delay)
        delay = min(delay * 1.5, max_delay)


async def _ws_listen(ws) -> None:
    """Process messages from the drone backend WebSocket."""
    async for raw in ws:
        try:
            msg = json.loads(raw)
        except json.JSONDecodeError:
            continue

        msg_type = msg.get("type", "")

        if msg_type == "status_update":
            drones_data = msg.get("drones", {})
            for drone_id, data in drones_data.items():
                await update_state(drone_id, data)

        elif msg_type in ("mission_completed", "order_delivered"):
            drone_id = msg.get("drone_id")
            if drone_id:
                await update_state(drone_id, {"status": "IDLE"})

        elif msg_type == "mission_failed":
            drone_id = msg.get("drone_id")
            if drone_id:
                await update_state(drone_id, {"status": "IDLE"})

        # Ignore other message types silently


# ---------------------------------------------------------------------------
# Fallback: HTTP polling (used when WS is unavailable for a drone)
# ---------------------------------------------------------------------------

async def poll_drone_status_http(drone_id: str) -> Optional[DroneState]:
    """
    One-shot HTTP fetch for a drone's status. Returns None on error.
    Useful for on-demand refreshes by the authorization layer.
    """
    try:
        async with httpx.AsyncClient(
            headers={"ngrok-skip-browser-warning": "true"}, timeout=5.0
        ) as client:
            r = await client.get(f"{DRONE_BACKEND_URL}/api/drones/{drone_id}/status")
        if r.status_code == 200:
            return await update_state(drone_id, r.json())
    except Exception as exc:
        log.debug(
            "http_poll_failed",
            event="http_poll_failed",
            service="fleet-ai",
            drone_id=drone_id,
            error=str(exc),
        )
    return None
