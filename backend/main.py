"""
main.py — Skyro Drone Control Backend (MAVSDK Edition)

FastAPI application on port 8080.

Architecture at 100+ drones:
  • Single asyncio event loop, workers=1 (multi-core → multiple containers).
  • DroneRegistry singleton: O(1) drone lookup, shared semaphore, stale checker.
  • Per-drone MAVSDKDroneAgent: 4 isolated telemetry tasks, DroneState cache.
  • MissionExecutor: delivery logic as asyncio.Task, full error recovery.
  • WebSocketManager: single broadcaster task, concurrent fan-out.
  • Shared httpx.AsyncClient: connection-pooled, timeout-bounded.
  • asyncio.Queue: background retry for orders PATCH failures.

All inter-service contract schemas and endpoint paths are FROZEN.
"""

from __future__ import annotations

import asyncio
import logging
import os
import signal
import uuid
from contextlib import asynccontextmanager
from typing import Any, Dict, Optional

import httpx
from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from drone_registry import DroneRegistry
from mission_executor import MissionExecutor
from models import (
    BatchConnectRequest,
    BatchConnectResponse,
    BatchConnectResult,
    ConnectRequest,
    ConnectResponse,
    DisconnectAllResponse,
    DroneSummaryResponse,
    ErrorResponse,
    LandingConfirmRequest,
    LandingConfirmResponse,
    LaunchRequest,
    LaunchResponse,
    ObstacleAlertRequest,
    ObstacleAlertResponse,
    StatusRequest,
    DroneListResponse,
    DroneListEntry,
)
from ws_manager import WebSocketManager

# ──────────────────────────────────────────────────────────────────────────────
# Logging & Configuration
# ──────────────────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("main")

FLEET_AI_URL: str = os.getenv("FLEET_AI_URL", "https://01ee-115-241-193-69.ngrok-free.app")
ORDERS_API_URL: str = os.getenv("ORDERS_API_URL", os.getenv("ORDERS_API_BASE", "https://fff8-2401-4900-cbd5-7c0d-d549-241c-a989-4b7a.ngrok-free.app"))

# Global singletons and states
registry = DroneRegistry()
ws_manager = WebSocketManager()

_http_client: Optional[httpx.AsyncClient] = None
_mission_executor: Optional[MissionExecutor] = None
_retry_queue: Optional[asyncio.Queue] = None
_accepting_missions = True

# ──────────────────────────────────────────────────────────────────────────────
# Background Retry Queue Processor
# ──────────────────────────────────────────────────────────────────────────────
async def _process_retry_queue() -> None:
    """
    Background loop: wakes up when items are added to _retry_queue,
    retries the PATCH order status, and sleeps on failure before re-queueing.
    """
    logger.info("Order status retry queue processor started.")
    try:
        while True:
            if _retry_queue is None:
                await asyncio.sleep(1.0)
                continue
            item = await _retry_queue.get()
            order_id = item["order_id"]
            payload = item["payload"]
            url = item["url"]
            
            logger.info("Retrying status update for order %s ...", order_id)
            success = False
            try:
                if _http_client:
                    resp = await _http_client.patch(url, json=payload)
                    if resp.is_success:
                        logger.info("Successfully retried status update for order %s.", order_id)
                        success = True
                    else:
                        logger.warning("Retry status update returned %d: %s", resp.status_code, resp.text)
            except Exception as exc:
                logger.warning("Retry status update failed: %s", exc)
                
            if not success:
                # Put it back to retry later
                await asyncio.sleep(5.0)
                await _retry_queue.put(item)
                
            _retry_queue.task_done()
    except asyncio.CancelledError:
        logger.info("Order status retry queue processor cancelled.")
    except Exception as exc:
        logger.error("Order status retry queue processor crashed: %s", exc, exc_info=True)

# ──────────────────────────────────────────────────────────────────────────────
# Lifespan manager
# ──────────────────────────────────────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    global _http_client, _mission_executor, _retry_queue
    logger.info("Skyro backend starting …")
    logger.info("[CONFIG] FLEET_AI_URL = %s", FLEET_AI_URL)
    logger.info("[CONFIG] ORDERS_API_URL = %s", ORDERS_API_URL)
    
    # 1. Start Drone Registry stale-drone checker
    registry.start()
    
    # 2. Initialize HTTP Client & Retry Queue
    _http_client = httpx.AsyncClient(timeout=10.0)
    _retry_queue = asyncio.Queue()
    _mission_executor = MissionExecutor(_http_client, _retry_queue)
    
    # 3. Start WS Broadcaster
    broadcaster_task = asyncio.create_task(
        ws_manager.start_broadcaster(registry),
        name="ws_broadcaster"
    )
    
    # 4. Start Retry Queue Processor
    retry_task = asyncio.create_task(
        _process_retry_queue(),
        name="retry_processor"
    )
    
    yield
    
    # Shutdown sequence
    logger.info("Skyro backend shutting down …")
    global _accepting_missions
    _accepting_missions = False
    
    # Cancel background tasks
    broadcaster_task.cancel()
    retry_task.cancel()
    await asyncio.gather(broadcaster_task, retry_task, return_exceptions=True)
    
    # Shutdown registry (RTLs in-flight and disconnects all)
    await registry.shutdown()
    
    # Close HTTP Client
    await _http_client.aclose()
    logger.info("Skyro backend shutdown complete.")

# ──────────────────────────────────────────────────────────────────────────────
# FastAPI App Setup
# ──────────────────────────────────────────────────────────────────────────────
app = FastAPI(
    title="Skyro Drone Control Backend (MAVSDK Edition)",
    description="FastAPI-based real-time control system for college campus drone fleet.",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS middleware (configurable via env CORS_ORIGINS; use '*' or comma-separated list)
CORS_ORIGINS_ENV = os.getenv("CORS_ORIGINS", "*")
if CORS_ORIGINS_ENV.strip() == "*":
    ALLOW_ORIGINS = ["*"]
else:
    ALLOW_ORIGINS = [o.strip() for o in CORS_ORIGINS_ENV.split(",") if o.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOW_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Helper to find agent or raise 404
def _get_agent_or_404(drone_id: str):
    try:
        return registry.get_drone(drone_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc))

# ──────────────────────────────────────────────────────────────────────────────
# REST Endpoints
# ──────────────────────────────────────────────────────────────────────────────
@app.get("/")
async def root() -> dict:
    return {
        "service": "Skyro Drone Control Backend (MAVSDK Edition)",
        "version": "1.0.0",
        "endpoints": {
            "connect": "POST /api/connect",
            "connect_batch": "POST /api/connect/batch",
            "launch": "POST /api/launch",
            "drones_list": "GET /api/drones",
            "status": "POST /api/status",
            "drones_status": "POST /api/drones/status",
            "all_drones_status": "GET /api/drones/status",
            "disconnect": "DELETE /api/drones/{drone_id}",
            "disconnect_all": "POST /api/drones/disconnect-all",
            "summary": "GET /api/drones/summary",
            "obstacle_alert": "POST /api/obstacles/alert",
            "landing_confirm": "POST /api/landing/confirm",
            "websocket": "WS /ws",
        }
    }

@app.post("/api/connect", response_model=ConnectResponse)
async def connect_drone(request: ConnectRequest):
    """Connect a single drone to the backend."""
    try:
        await registry.add_drone(request.drone_id, request.connection_string)
        return ConnectResponse(
            success=True,
            drone_id=request.drone_id,
            status="CONNECTED"
        )
    except Exception as exc:
        logger.error("[%s] Connection failed: %s", request.drone_id, exc)
        return ConnectResponse(
            success=False,
            drone_id=request.drone_id,
            status="FAILED",
            error=str(exc)
        )

@app.post("/api/connect/batch", response_model=BatchConnectResponse)
async def connect_batch(request: BatchConnectRequest):
    """Connect a batch of drones concurrently."""
    entries = [{"drone_id": d.drone_id, "connection_string": d.connection_string} for d in request.drones]
    results = await registry.connect_batch(entries)
    
    connected = sum(1 for r in results if r["success"])
    failed = sum(1 for r in results if not r["success"])
    
    response_results = [
        BatchConnectResult(
            drone_id=r["drone_id"],
            success=r["success"],
            error=r["error"]
        )
        for r in results
    ]
    return BatchConnectResponse(
        results=response_results,
        connected=connected,
        failed=failed
    )

@app.post("/api/launch", response_model=LaunchResponse)
async def launch_mission(request: LaunchRequest):
    """
    Start a delivery mission. Returns IMMEDIATELY — mission runs as background
    asyncio.Task. Any failure is caught by MissionExecutor and the task.
    """
    if not _accepting_missions:
        raise HTTPException(status_code=503, detail="Backend is shutting down.")

    # Start the order launch/assign workflow as a background task
    async def _order_launch_wrapper():
        try:
            # Step 0: Resolve block name from coordinates
            from mission_executor import get_block_name
            block_name = get_block_name(request.delivery_lat, request.delivery_lon)

            logger.info("[Order:%s] Starting launch/assign workflow for block '%s'...", request.order_id, block_name)

            # Step 1: Wait/retry loop until landing block, home pad, and IDLE drone are free
            while True:
                try:
                    if _http_client is None:
                        await asyncio.sleep(1.0)
                        continue
                        
                    # 1. Check if landing zone is busy
                    resp = await _http_client.get(f"{FLEET_AI_URL}/zone-status")
                    if resp.status_code == 200:
                        zones = resp.json()
                        zone_info = next((z for z in zones if z["zone"] == block_name), None)
                        if zone_info and zone_info.get("occupied", False):
                            logger.info("[Order:%s] Landing zone '%s' is busy. Waiting 5s...", request.order_id, block_name)
                            await asyncio.sleep(5.0)
                            continue
                    
                    # 3. Assign a drone using Fleet AI scoring
                    resp = await _http_client.post(
                        f"{FLEET_AI_URL}/assign-drone",
                        json={
                            "orderId": str(request.order_id),
                            "destination": block_name,
                            "priority": 1
                        }
                    )
                    if resp.status_code == 200:
                        data = resp.json()
                        drone_id = data.get("droneId")
                        if drone_id:
                            # Verify the assigned drone is online and IDLE
                            try:
                                agent = registry.get_drone(drone_id)
                                if agent.state.is_online and agent.state.status == "IDLE":
                                    logger.info("[Order:%s] Fleet AI assigned drone %s.", request.order_id, drone_id)
                                    break
                                else:
                                    logger.info("[Order:%s] Fleet AI assigned drone %s, but it is not IDLE/online. Waiting 5s...", request.order_id, drone_id)
                            except KeyError:
                                logger.info("[Order:%s] Fleet AI assigned drone %s, but it is not found in registry. Waiting 5s...", request.order_id, drone_id)
                        else:
                            logger.info("[Order:%s] Fleet AI returned no droneId. Waiting 5s...", request.order_id)
                    else:
                        logger.info("[Order:%s] Fleet AI drone assignment failed: %d. Waiting 5s...", request.order_id, resp.status_code)
                        
                    await asyncio.sleep(5.0)
                    continue
                except Exception as exc:
                    logger.warning("[Order:%s] Error checking Fleet AI statuses: %r. Retrying...", request.order_id, exc, exc_info=True)
                    await asyncio.sleep(5.0)
                    continue

            # Step 2: Start the mission
            mission_id = str(request.order_id)
            
            async def _mission_wrapper():
                if _mission_executor:
                    await _mission_executor.execute(
                        agent=agent,
                        order_id=str(request.order_id),
                        delivery_lat=request.delivery_lat,
                        delivery_lon=request.delivery_lon,
                        delivery_alt=request.delivery_alt,
                    )
            
            agent.mission_task = asyncio.create_task(
                _mission_wrapper(), name=f"mission:{drone_id}:{mission_id}"
            )
            
            def _on_mission_done(task: asyncio.Task) -> None:
                if task.cancelled():
                    logger.info("[%s] Mission task %s was cancelled.", agent.drone_id, mission_id)
                    return
                exc = task.exception()
                if exc and not isinstance(exc, asyncio.CancelledError):
                    logger.error(
                        "[%s] Mission task %s raised unhandled exception: %s",
                        agent.drone_id,
                        mission_id,
                        exc,
                        exc_info=True,
                    )
            
            agent.mission_task.add_done_callback(_on_mission_done)
            logger.info("[Order:%s] Successfully assigned and launched drone %s.", request.order_id, drone_id)

            # Notify orders service of successful launch and drone assignment
            try:
                if _http_client:
                    url = f"{ORDERS_API_URL}/api/orders/{request.order_id}"
                    await _http_client.patch(url, json={"status": "En Route", "droneId": drone_id})
                    logger.info("[Order:%s] Patched orders service to 'En Route' with droneId '%s'.", request.order_id, drone_id)
            except Exception as patch_exc:
                logger.warning("[Order:%s] Could not patch order assignment to orders service: %s", request.order_id, patch_exc)
        except Exception as exc:
            logger.error("[Order:%s] Error in launch wrapper: %s", request.order_id, exc, exc_info=True)
            # Notify orders service of failure
            try:
                if _http_client:
                    url = f"{ORDERS_API_URL}/api/orders/{request.order_id}"
                    await _http_client.patch(url, json={"status": "Failed"})
            except Exception as patch_exc:
                logger.warning("[Order:%s] Could not patch failed order: %s", request.order_id, patch_exc)

    # Queue the launcher wrapper task
    asyncio.create_task(_order_launch_wrapper())

    return LaunchResponse(
        success=True,
        mission_id=str(request.order_id),
        drone_id=request.drone_id or ""
    )

@app.get("/api/drones", response_model=DroneListResponse)
async def list_drones():
    """List all connected drones."""
    drones_list = [
        DroneListEntry(
            id=agent.drone_id,
            status=agent.state.status,
            connection_string=agent.state.connection_string
        )
        for agent in registry.get_all_agents().values()
    ]
    return DroneListResponse(drones=drones_list)

@app.post("/api/drones/status")
@app.post("/api/status")
async def get_drone_status(request: StatusRequest):
    """Get the current status of a specific drone."""
    agent = _get_agent_or_404(request.drone_id)
    return agent.get_state_snapshot()

@app.get("/api/drones/status")
async def all_drones_status():
    """
    Full DroneState for all registered drones.
    Fleet AI polls this endpoint. Reads cache only — no MAVSDK calls.
    """
    return {"drones": registry.get_all_states_dict()}

@app.delete("/api/drones/{drone_id}")
async def disconnect_drone(drone_id: str):
    """Disconnect a specific drone."""
    try:
        await registry.remove_drone(drone_id)
        return {"success": True, "message": f"Drone {drone_id} disconnected."}
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc))

@app.post("/api/drones/disconnect-all", response_model=DisconnectAllResponse)
async def disconnect_all_drones():
    """Disconnect all drones gracefully (RTL first)."""
    count = await registry.disconnect_all()
    return DisconnectAllResponse(disconnected=count)

@app.get("/api/drones/summary", response_model=DroneSummaryResponse)
async def get_drones_summary():
    """Return summary metrics for all registered drones."""
    agents = registry.get_all_agents().values()
    total = len(agents)
    
    idle = sum(1 for a in agents if a.state.status == "IDLE")
    in_flight = sum(1 for a in agents if a.state.status == "IN_FLIGHT")
    returning_home = sum(1 for a in agents if a.state.status == "RETURNING_HOME")
    offline = sum(1 for a in agents if a.state.status == "OFFLINE")
    charging = sum(1 for a in agents if a.state.status == "CHARGING")
    failed = sum(1 for a in agents if a.state.status in ("FAILED", "MAINTENANCE"))
    
    return DroneSummaryResponse(
        total=total,
        idle=idle,
        in_flight=in_flight,
        returning_home=returning_home,
        offline=offline,
        charging=charging,
        failed=failed
    )

@app.post("/api/obstacles/alert", response_model=ObstacleAlertResponse)
async def obstacle_alert(request: ObstacleAlertRequest):
    """Handle real-time obstacle alerts."""
    logger.warning(
        "[%s] Obstacle alert: type=%s, distance=%.1f m",
        request.drone_id,
        request.obstacle_type,
        request.distance_m
    )
    action_taken = "NONE"
    if request.distance_m < 5.0:
        try:
            agent = registry.get_drone(request.drone_id)
            if agent.mission_task and not agent.mission_task.done():
                agent.mission_task.cancel()
            await agent.emergency_rtl()
            action_taken = "RTL"
        except Exception as exc:
            logger.error("[%s] Failed to trigger RTL on obstacle: %s", request.drone_id, exc)
            action_taken = "FAILED_TO_RTL"
            
    return ObstacleAlertResponse(action_taken=action_taken)

@app.post("/api/landing/confirm", response_model=LandingConfirmResponse)
async def confirm_landing(request: LandingConfirmRequest):
    """Confirm landing accuracy."""
    logger.info(
        "[%s] Landing confirm: method=%s, accuracy=%.2f m",
        request.drone_id,
        request.method,
        request.accuracy_m
    )
    return LandingConfirmResponse(confirmed=True)


# ──────────────────────────────────────────────────────────────────────────────
# Simulation Endpoints (Bypass MAVSDK — for Windows testing without ArduPilot)
# ──────────────────────────────────────────────────────────────────────────────

# In-memory simulated drone states (keyed by drone_id)
_sim_states: Dict[str, Any] = {}

@app.post("/api/sim/inject-drone")
async def sim_inject_drone(data: dict):
    """
    [SIM] Register and update a simulated drone in the registry WITHOUT a real
    MAVSDK connection. The drone appears as IDLE with full GPS coordinates and
    battery. The WS broadcaster includes it in every status_update broadcast,
    so fleet-ai sees it as a real drone and can assign orders.

    This is the recommended way to simulate multiple drones on Windows without
    ArduPilot or WSL2.

    Required body:
        {
            "drone_id": "D-01",
            "lat": 16.462635,
            "lon": 80.506471,
            "alt": 0.0,
            "battery": 85.0,
            "status": "IDLE"
        }
    """
    from models import DroneState as BackendDroneState
    from datetime import datetime

    drone_id = data.get("drone_id") or data.get("droneId")
    if not drone_id:
        raise HTTPException(status_code=400, detail="drone_id is required")

    # Upsert the simulated state in our local map
    _sim_states[drone_id] = data

    # Also inject directly into the registry's drone state if it already exists
    if drone_id in registry._drones:
        agent = registry._drones[drone_id]
        agent.state.lat = float(data.get("lat", agent.state.lat))
        agent.state.lon = float(data.get("lon", agent.state.lon))
        agent.state.altitude = float(data.get("alt", agent.state.altitude))
        agent.state.battery = float(data.get("battery", agent.state.battery))
        agent.state.status = str(data.get("status", agent.state.status))
        agent.state.is_online = True
        agent.state.last_seen = datetime.utcnow()
    else:
        # Create a stub DroneState and register it directly
        stub_state = BackendDroneState(
            drone_id=drone_id,
            status=str(data.get("status", "IDLE")),
            battery=float(data.get("battery", 85.0)),
            lat=float(data.get("lat", 16.462635)),
            lon=float(data.get("lon", 80.506471)),
            altitude=float(data.get("alt", 0.0)),
            is_online=True,
            last_seen=datetime.utcnow(),
            connection_string="sim://simulated",
            flight_mode="READY",
        )
        # Inject a stub agent that holds this state into the registry
        # We do this by creating a minimal mock that wraps the state
        from drone_agent import MAVSDKDroneAgent
        import asyncio

        # Use a dummy semaphore that never blocks
        dummy_sem = asyncio.Semaphore(999)
        agent = MAVSDKDroneAgent.__new__(MAVSDKDroneAgent)
        agent.drone_id = drone_id
        agent._connection_string = "sim://simulated"
        agent._semaphore = dummy_sem
        agent._grpc_port = 0
        agent.state = stub_state
        agent.system = None
        agent.mission_task = None
        agent._telemetry_tasks = []
        registry._drones[drone_id] = agent

    logger.info(f"[SIM] Drone {drone_id} injected: status={data.get('status','IDLE')} battery={data.get('battery',85)}%")
    return {"ok": True, "drone_id": drone_id, "status": data.get("status", "IDLE")}


@app.get("/api/sim/drones")
async def sim_list_drones():
    """[SIM] List all currently simulated drones."""
    return {"simulated": list(_sim_states.keys()), "states": _sim_states}



@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """
    Single WebSocket endpoint. Fleet AI and frontend connect here.
    Broadcaster (R8) fans out telemetry every 2 s to all clients.
    """
    await ws_manager.connect(websocket)
    try:
        while True:
            # Keep the connection alive
            await websocket.receive_text()
    except WebSocketDisconnect:
        pass
    except Exception as exc:
        logger.debug("WebSocket connection closed with error: %s", exc)
    finally:
        await ws_manager.disconnect(websocket)

# ──────────────────────────────────────────────────────────────────────────────
# Run script
# ──────────────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import uvicorn
    host = os.getenv("HOST", "127.0.0.1")
    try:
        port = int(os.getenv("PORT", "8080"))
    except ValueError:
        port = 8080
    logger.info(f"Starting server on http://{host}:{port}")
    uvicorn.run(app, host=host, port=port, log_level="info")