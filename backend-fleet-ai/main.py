"""
backend-fleet-ai/main.py — Fleet AI FastAPI Application (Redesigned)

Service: Skyro Fleet AI  v2.0
Port: 8002

Flow: Frontend → Orders Service → Fleet AI → Drone Backend → Drone

Startup sequence (lifespan, all phases must complete before orders accepted):
  Phase 1: ping_redis()                    — fail fast if Redis is down
  Phase 2: boot_pad_reconstruction()       — restore home pad locks from PostgreSQL
  Phase 3: prewarm_cache()                 — pre-load location data into Redis
  Phase 4: rebuild_collision_from_active() — restore R-tree from IN_FLIGHT drones
  Phase 5: start background tasks          — ws sync, stale cleaner, cooldown monitor, midnight reset
  Phase 6: _accepting_orders = True        ← orders only processed after this point

_accepting_orders is checked on every assignment endpoint.
"""

from __future__ import annotations

import asyncio
import datetime
import os
import time
from contextlib import asynccontextmanager
from typing import List, Optional

import structlog
from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

import landing as landing_module
import state_manager
import traffic as traffic_module
from collision import get_collision_engine
from landing import (
    boot_pad_reconstruction,
    init_home_locations,
    on_drone_home_landing_confirmed,
    release_delivery_lock,
    stale_reservation_cleaner,
)
from location_cache import prewarm_cache
from models import (
    AssignDroneRequest,
    AssignDroneResponse,
    AuthorizeMissionRequest,
    DroneMetricsResponse,
    FleetStatusResponse,
    HomeLandingRequest,
    RecordDeliveryRequest,
    RecordFlightTimeRequest,
)
from redis_client import close_redis, get_redis, ping_redis
from scheduler import NoEligibleDroneError, get_scheduler

import authorization as auth_module
import traffic as traffic_router_module

# ─────────────────────────────────────────────────────────────────────────────
# structlog configuration
# ─────────────────────────────────────────────────────────────────────────────

class SafeBoundLogger(structlog.stdlib.BoundLogger):
    def _proxy(self, method_name, *args, **kw):
        if args and "event" in kw:
            kw.pop("event")
        method = getattr(super(), method_name)
        return method(*args, **kw)

    def debug(self, *args, **kw): return self._proxy("debug", *args, **kw)
    def info(self, *args, **kw): return self._proxy("info", *args, **kw)
    def warning(self, *args, **kw): return self._proxy("warning", *args, **kw)
    def error(self, *args, **kw): return self._proxy("error", *args, **kw)
    def critical(self, *args, **kw): return self._proxy("critical", *args, **kw)
    def exception(self, *args, **kw): return self._proxy("exception", *args, **kw)
    def fatal(self, *args, **kw): return self._proxy("fatal", *args, **kw)
    def log(self, *args, **kw): return self._proxy("log", *args, **kw)
    def warn(self, *args, **kw): return self._proxy("warn", *args, **kw)

structlog.configure(
    processors=[
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.JSONRenderer(),
    ],
    wrapper_class=SafeBoundLogger,
    context_class=dict,
    logger_factory=structlog.stdlib.LoggerFactory(),
)

log = structlog.get_logger("fleet-ai")

# ─────────────────────────────────────────────────────────────────────────────
# Global state
# ─────────────────────────────────────────────────────────────────────────────

_accepting_orders: bool = False
CORS_ORIGINS: str = os.getenv("CORS_ORIGINS", "*")


# ─────────────────────────────────────────────────────────────────────────────
# WebSocket Manager
# ─────────────────────────────────────────────────────────────────────────────

class FleetWSManager:
    """Manages frontend WebSocket connections and structured event broadcasting."""

    def __init__(self) -> None:
        self._connections: List[WebSocket] = []

    async def connect(self, ws: WebSocket) -> None:
        await ws.accept()
        self._connections.append(ws)
        log.debug("ws_client_connected", event="ws_client_connected", service="fleet-ai",
                  total=len(self._connections))

    def disconnect(self, ws: WebSocket) -> None:
        try:
            self._connections.remove(ws)
        except ValueError:
            pass
        log.debug("ws_client_disconnected", event="ws_client_disconnected", service="fleet-ai",
                  total=len(self._connections))

    async def broadcast_json(self, data: dict) -> None:
        """Fan-out a JSON message to all connected WS clients."""
        dead: List[WebSocket] = []
        for ws in list(self._connections):
            try:
                await ws.send_json(data)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.disconnect(ws)

    async def broadcast_text(self, text: str) -> None:
        dead: List[WebSocket] = []
        for ws in list(self._connections):
            try:
                await ws.send_text(text)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.disconnect(ws)


fleet_ws_manager = FleetWSManager()


def _make_ws_event(
    event_type: str,
    drone_id: Optional[str] = None,
    order_id: Optional[str] = None,
    data: Optional[dict] = None,
) -> dict:
    """Build a structured WebSocket event envelope."""
    event: dict = {
        "type":      event_type,
        "timestamp": datetime.datetime.utcnow().isoformat() + "Z",
        "service":   "fleet-ai",
        "data":      data or {},
    }
    if drone_id:
        event["drone_id"] = drone_id
    if order_id:
        event["order_id"] = order_id
    return event


# ─────────────────────────────────────────────────────────────────────────────
# Background tasks
# ─────────────────────────────────────────────────────────────────────────────

async def _fleet_status_pusher() -> None:
    """Push fleet status to WS clients every 2 seconds."""
    while True:
        await asyncio.sleep(2)
        try:
            states = await state_manager.get_all_states()
            conflicts = traffic_module.detect_conflicts(states)
            from landing import get_home_status
            home = await get_home_status()
            await fleet_ws_manager.broadcast_json({
                "type":     "fleet_update",
                "timestamp": datetime.datetime.utcnow().isoformat() + "Z",
                "service":  "fleet-ai",
                "drones":   {did: s.dict() for did, s in states.items()},
                "conflicts": [c.dict() for c in conflicts],
                "home_status": home,
            })
        except Exception as exc:
            log.warning("fleet_pusher_error", event="fleet_pusher_error",
                        service="fleet-ai", error=str(exc))


async def _cooldown_monitor() -> None:
    """
    Every 30s: scan drone_state:* keys in Redis with value COOLDOWN.
    For each expired cooldown (TTL <= 0), set state to IDLE and emit WS event.
    """
    while True:
        await asyncio.sleep(30)
        try:
            r = await get_redis()
            keys = await r.keys("drone_state:*")
            for key in keys:
                val = await r.get(key)
                if val != "COOLDOWN":
                    continue
                ttl = await r.ttl(key)
                if ttl <= 0:
                    drone_id = key.replace("drone_state:", "")
                    await r.set(key, "IDLE")
                    log.info("drone_cooldown_ended", event="drone_cooldown_ended",
                             service="fleet-ai", drone_id=drone_id)
                    await fleet_ws_manager.broadcast_json(
                        _make_ws_event("drone_cooldown_ended", drone_id=drone_id)
                    )
        except Exception as exc:
            log.warning("cooldown_monitor_error", event="cooldown_monitor_error",
                        service="fleet-ai", error=str(exc))


async def _midnight_reset() -> None:
    """
    Every 60s: check if the date has rolled over since last reset.
    If so, DEL all deliveries_today:* and flight_minutes_today:* keys.
    """
    while True:
        await asyncio.sleep(60)
        try:
            r = await get_redis()
            today_str = datetime.datetime.utcnow().date().isoformat()
            last_reset = await r.get("deliveries_today_reset_date")
            if last_reset != today_str:
                # Date has changed — wipe counters
                del_keys = await r.keys("deliveries_today:*")
                flight_keys = await r.keys("flight_minutes_today:*")
                all_keys = del_keys + flight_keys
                if all_keys:
                    await r.delete(*all_keys)
                await r.set("deliveries_today_reset_date", today_str)
                log.info("midnight_reset_done", event="midnight_reset_done",
                         service="fleet-ai", date=today_str,
                         keys_deleted=len(all_keys))
        except Exception as exc:
            log.warning("midnight_reset_error", event="midnight_reset_error",
                        service="fleet-ai", error=str(exc))


# ─────────────────────────────────────────────────────────────────────────────
# FastAPI lifespan
# ─────────────────────────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    global _accepting_orders
    _accepting_orders = False

    log.info("fleet_ai_startup_begin", event="fleet_ai_startup_begin", service="fleet-ai")

    # Phase 1: Redis health check
    while True:
        try:
            await ping_redis()
            log.info("startup_phase1_redis_ok", event="startup_phase1_redis_ok", service="fleet-ai")
            break
        except RuntimeError as exc:
            log.critical("startup_redis_unavailable", event="startup_redis_unavailable",
                         service="fleet-ai", error=str(exc))
            # Emit WS alert for any connected clients (none yet, but for completeness)
            await fleet_ws_manager.broadcast_json({"type": "redis_unavailable", "service": "fleet-ai"})
            await asyncio.sleep(10)

    # Phase 2: Boot pad reconstruction
    while True:
        try:
            n = await boot_pad_reconstruction()
            log.info("startup_phase2_pads_reconstructed", event="startup_phase2_pads_reconstructed",
                     service="fleet-ai", pads=n)
            break
        except RuntimeError as exc:
            log.critical("startup_pad_reconstruction_failed",
                         event="startup_pad_reconstruction_failed",
                         service="fleet-ai", error=str(exc))
            await asyncio.sleep(10)

    # Phase 3: Pre-warm location cache
    await prewarm_cache()
    log.info("startup_phase3_location_cache_warmed", event="startup_phase3_location_cache_warmed",
             service="fleet-ai")

    # Phase 4: Rebuild collision engine from IN_FLIGHT drones
    await traffic_module.rebuild_collision_from_active()
    log.info("startup_phase4_collision_rebuilt", event="startup_phase4_collision_rebuilt",
             service="fleet-ai")

    # Phase 5: Start background tasks
    await state_manager.start_background_sync()
    asyncio.create_task(stale_reservation_cleaner(), name="stale_cleaner")
    asyncio.create_task(_fleet_status_pusher(), name="fleet_status_pusher")
    asyncio.create_task(_cooldown_monitor(), name="cooldown_monitor")
    asyncio.create_task(_midnight_reset(), name="midnight_reset")
    log.info("startup_phase5_background_tasks_started",
             event="startup_phase5_background_tasks_started", service="fleet-ai")

    # Phase 6: Accept orders
    _accepting_orders = True
    log.info("fleet_ai_ready", event="fleet_ai_ready", service="fleet-ai",
             message="Fleet AI is fully initialised and accepting orders.")

    yield  # ← app is running

    # Shutdown
    _accepting_orders = False
    await close_redis()
    log.info("fleet_ai_shutdown", event="fleet_ai_shutdown", service="fleet-ai")


# ─────────────────────────────────────────────────────────────────────────────
# FastAPI app
# ─────────────────────────────────────────────────────────────────────────────

app = FastAPI(
    title="Skyro Fleet AI",
    version="2.0.0",
    description="AI-powered drone fleet management for Skyro campus delivery.",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[CORS_ORIGINS] if CORS_ORIGINS != "*" else ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register sub-routers
from landing import router as landing_router
from traffic import router as traffic_router
from authorization import router as auth_router

app.include_router(landing_router, tags=["landing"])
app.include_router(traffic_router, tags=["traffic"])
app.include_router(auth_router, tags=["authorization"])


# ─────────────────────────────────────────────────────────────────────────────
# Guards
# ─────────────────────────────────────────────────────────────────────────────

def _check_accepting_orders():
    if not _accepting_orders:
        raise HTTPException(
            status_code=503,
            detail="Fleet AI is initialising, please retry in a few seconds.",
        )


# ─────────────────────────────────────────────────────────────────────────────
# Core endpoints
# ─────────────────────────────────────────────────────────────────────────────

@app.get("/", summary="Fleet AI metadata")
async def root():
    return {
        "service": "Skyro Fleet AI",
        "version": "2.0.0",
        "accepting_orders": _accepting_orders,
        "endpoints": [
            "POST /assign-drone",
            "GET  /fleet-status",
            "POST /authorize-mission",
            "POST /reserve-landing",
            "POST /landing/confirm",
            "GET  /zone-status",
            "POST /reserve-home-location",
            "POST /release-home-location",
            "GET  /home-status",
            "POST /on-home-landing",
            "POST /record-flight-time",
            "POST /record-delivery",
            "GET  /drone-metrics/{drone_id}",
            "GET  /conflicts",
            "POST /obstacle-alert",
            "WS   /ws",
        ],
    }


@app.post("/assign-drone", response_model=AssignDroneResponse, summary="AI drone assignment")
async def assign_drone(request: AssignDroneRequest):
    """
    Full Part B lock flow:
    1. Score and select best drone via scheduler
    2. Acquire Redis delivery lock (SET NX, polls up to 120s)
    3. Check home pad availability; re-score if needed
    4. Acquire home pad lock (SET NX EX 600s)
    5. Register trajectory in collision engine
    6. Return assignment with score_breakdown
    """
    _check_accepting_orders()

    scheduler = get_scheduler()
    drone_states = await state_manager.get_all_states()

    # ── Step 1: Score and select drone ────────────────────────────────────────
    try:
        drone_id, breakdown = await scheduler.assign_async(request, drone_states)
    except NoEligibleDroneError as exc:
        log.warning("order_assignment_failed", event="order_assignment_failed",
                    service="fleet-ai", order_id=request.orderId, reason=str(exc))
        await fleet_ws_manager.broadcast_json(
            _make_ws_event("order_assignment_failed", order_id=request.orderId,
                           data={"reason": str(exc)})
        )
        raise HTTPException(status_code=503, detail=str(exc))

    # ── Step 2: Acquire delivery zone lock ────────────────────────────────────
    acquired = await landing_module.acquire_delivery_lock(request.destination, drone_id)
    if not acquired:
        reason = f"Delivery zone '{request.destination}' did not clear within 120s."
        log.warning("order_assignment_failed_zone_timeout", event="order_assignment_failed",
                    service="fleet-ai", order_id=request.orderId, drone_id=drone_id,
                    reason=reason)
        await fleet_ws_manager.broadcast_json(
            _make_ws_event("order_assignment_failed", order_id=request.orderId,
                           drone_id=drone_id, data={"reason": reason})
        )
        raise HTTPException(status_code=503, detail=reason)

    # ── Step 3: Check home pad and acquire lock ───────────────────────────────
    from location_cache import get_home_locations
    home_locs = await get_home_locations()

    # Find which home pad this drone currently holds (if any)
    drone_pad_id: Optional[str] = None
    r = await get_redis()
    for loc in home_locs:
        occupant = await r.get(f"home_pad_lock:{loc['name']}")
        if occupant == drone_id:
            drone_pad_id = loc["name"]
            break

    if drone_pad_id:
        # Drone already has a pad — upgrade its lock to mission TTL
        await landing_module.acquire_home_pad_lock(drone_pad_id, drone_id, persistent=False)
    else:
        # Try to find any free pad
        free_pad = None
        for loc in home_locs:
            occupant = await r.get(f"home_pad_lock:{loc['name']}")
            if occupant is None:
                free_pad = loc
                break

        if free_pad:
            acquired_home = await landing_module.acquire_home_pad_lock(
                free_pad["name"], drone_id, persistent=False
            )
            if acquired_home:
                drone_pad_id = free_pad["name"]
            else:
                # Race condition: all pads taken, fallback — re-score for home-pad-available drones
                await release_delivery_lock(request.destination)
                try:
                    drone_id, breakdown = await scheduler.assign_async(
                        request, drone_states, home_pad_available_only=True
                    )
                except NoEligibleDroneError as exc:
                    await fleet_ws_manager.broadcast_json(
                        _make_ws_event("order_assignment_failed", order_id=request.orderId,
                                       data={"reason": str(exc)})
                    )
                    raise HTTPException(status_code=503, detail=str(exc))
                # Re-acquire delivery lock for new drone
                acquired = await landing_module.acquire_delivery_lock(request.destination, drone_id)
                if not acquired:
                    raise HTTPException(status_code=503,
                                        detail="Delivery zone unavailable after drone re-selection.")
        # If no free pad, proceed without — drone will reserve one during mission

    # ── Step 4: Register trajectory in collision engine ───────────────────────
    drone_state = drone_states.get(drone_id)
    if drone_state:
        from location_cache import resolve_location_coords
        try:
            dest_lat, dest_lon = await resolve_location_coords(request.destination)
        except KeyError:
            dest_lat, dest_lon = drone_state.lat, drone_state.lon

        from scheduler import haversine_km
        TAKEOFF_ALT = 20.0
        alt_offset, should_loiter = await traffic_module.register_drone_trajectory(
            drone_id=drone_id,
            start_lat=drone_state.lat,
            start_lon=drone_state.lon,
            start_alt=0.0,
            end_lat=dest_lat,
            end_lon=dest_lon,
            end_alt=TAKEOFF_ALT,
            order_priority=request.priority,
        )
        if should_loiter:
            log.info("trajectory_registered_loiter_pending",
                     event="trajectory_registered_loiter_pending",
                     service="fleet-ai", drone_id=drone_id, order_id=request.orderId)
    else:
        alt_offset = 0.0

    # ── Step 5: Compute ETA and return ────────────────────────────────────────
    eta = 120  # default ETA
    if drone_state:
        from location_cache import resolve_location_coords
        try:
            dest_lat, dest_lon = await resolve_location_coords(request.destination)
            from scheduler import eta_seconds
            eta = eta_seconds(drone_state, dest_lat, dest_lon)
        except Exception:
            pass

    confidence = round(min(1.0, breakdown.total / 100.0), 3)

    log.info("drone_assigned", event="drone_assigned", service="fleet-ai",
             order_id=request.orderId, drone_id=drone_id,
             score=breakdown.total, confidence=confidence, eta_s=eta)

    return AssignDroneResponse(
        droneId=drone_id,
        eta=eta,
        confidence=confidence,
        score=breakdown.total,
        score_breakdown=breakdown,
    )


@app.get("/fleet-status", response_model=FleetStatusResponse, summary="Full fleet snapshot")
async def fleet_status():
    states = await state_manager.get_all_states()
    from traffic import detect_conflicts
    conflicts = detect_conflicts(states)
    from landing import get_zone_status
    zones = await get_zone_status()
    active_count = sum(1 for s in states.values() if s.status not in ("IDLE", "OFFLINE"))
    return FleetStatusResponse(
        drones=states,
        zones=zones,
        conflicts=conflicts,
        total_active=active_count,
    )


# ─────────────────────────────────────────────────────────────────────────────
# New endpoints — flight time, delivery counter, drone metrics, home landing
# ─────────────────────────────────────────────────────────────────────────────

@app.post("/on-home-landing", summary="Notify Fleet AI of drone home landing")
async def on_home_landing_endpoint(req: HomeLandingRequest):
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

    # Deregister trajectory from collision engine
    await traffic_module.deregister_drone_trajectory(req.droneId)

    return {"confirmed": True, "droneId": req.droneId, "pad_id": req.pad_id}


@app.post("/record-flight-time", summary="Record drone flight time")
async def record_flight_time(req: RecordFlightTimeRequest):
    """Increment flight_minutes_today:{drone_id} in Redis by req.minutes."""
    try:
        r = await get_redis()
        new_val = await r.incrbyfloat(f"flight_minutes_today:{req.droneId}", req.minutes)
        log.info("flight_time_recorded", event="flight_time_recorded", service="fleet-ai",
                 drone_id=req.droneId, minutes_added=req.minutes, total=new_val)
        return {"droneId": req.droneId, "flight_minutes_today": float(new_val)}
    except Exception as exc:
        log.warning("flight_time_record_error", event="flight_time_record_error",
                    service="fleet-ai", drone_id=req.droneId, error=str(exc))
        raise HTTPException(status_code=503, detail=f"Redis unavailable: {exc}")


@app.post("/record-delivery", summary="Record drone completed delivery")
async def record_delivery(req: RecordDeliveryRequest):
    """Increment deliveries_today:{drone_id} in Redis."""
    try:
        r = await get_redis()
        new_val = await r.incr(f"deliveries_today:{req.droneId}")
        log.info("delivery_recorded", event="delivery_recorded", service="fleet-ai",
                 drone_id=req.droneId, deliveries_today=new_val)
        return {"droneId": req.droneId, "deliveries_today": int(new_val)}
    except Exception as exc:
        log.warning("delivery_record_error", event="delivery_record_error",
                    service="fleet-ai", drone_id=req.droneId, error=str(exc))
        raise HTTPException(status_code=503, detail=f"Redis unavailable: {exc}")


@app.get("/drone-metrics/{drone_id}", response_model=DroneMetricsResponse,
         summary="Get drone daily metrics")
async def drone_metrics(drone_id: str):
    """Return flight_minutes_today, deliveries_today, cooldown state, last_landed_at."""
    try:
        r = await get_redis()
        flight_raw = await r.get(f"flight_minutes_today:{drone_id}")
        delivery_raw = await r.get(f"deliveries_today:{drone_id}")
        state_raw = await r.get(f"drone_state:{drone_id}")
        landed_raw = await r.get(f"last_landed_at:{drone_id}")

        return DroneMetricsResponse(
            droneId=drone_id,
            flight_minutes_today=float(flight_raw or 0),
            deliveries_today=int(delivery_raw or 0),
            cooldown_state=state_raw if state_raw in ("IDLE", "COOLDOWN") else "IDLE",
            last_landed_at=float(landed_raw) if landed_raw else None,
        )
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"Redis unavailable: {exc}")


# ─────────────────────────────────────────────────────────────────────────────
# SIM endpoints
# ─────────────────────────────────────────────────────────────────────────────

@app.post("/api/sim/inject-state", summary="[SIM] Inject drone telemetry")
async def sim_inject_state(data: dict):
    drone_id = data.get("drone_id") or data.get("droneId")
    if not drone_id:
        raise HTTPException(status_code=400, detail="drone_id is required")
    state = await state_manager.update_state(drone_id, data)
    return state.dict()


@app.get("/api/sim/fleet-state", summary="[SIM] Get current fleet state")
async def sim_fleet_state():
    states = await state_manager.get_all_states()
    return {did: s.dict() for did, s in states.items()}


# ─────────────────────────────────────────────────────────────────────────────
# WebSocket
# ─────────────────────────────────────────────────────────────────────────────

@app.websocket("/ws")
async def fleet_ws_endpoint(ws: WebSocket):
    await fleet_ws_manager.connect(ws)
    try:
        while True:
            await ws.receive_text()
    except WebSocketDisconnect:
        fleet_ws_manager.disconnect(ws)
    except Exception:
        fleet_ws_manager.disconnect(ws)


# ─────────────────────────────────────────────────────────────────────────────
# Entrypoint
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "main:app",
        host=os.getenv("HOST", "0.0.0.0"),
        port=int(os.getenv("PORT", "8002")),
        reload=False,
        workers=1,
    )
