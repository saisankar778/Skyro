"""
drone_registry.py - DroneRegistry singleton

Owns all MAVSDKDroneAgent instances.  Provides:
  * O(1) lookup by drone_id  (R5)
  * Shared asyncio.Semaphore capped at MAX_CONCURRENT_CONNECTIONS  (R2)
  * Background stale-drone detection every 5 s  (R6)
  * Batch-connect helper using asyncio.gather  (new admin endpoint)
  * Graceful disconnect-all with RTL for in-flight drones  (R10)
"""

from __future__ import annotations

import asyncio
import logging
import os
from datetime import datetime, timedelta
from typing import Dict, List, Optional

from drone_agent import MAVSDKDroneAgent
from models import DroneState

logger = logging.getLogger("drone_registry")

# ------------------------------------------------------------------------------
# Environment knobs
# ------------------------------------------------------------------------------
MAX_CONCURRENT_CONNECTIONS: int = int(os.getenv("MAX_CONCURRENT_DRONES", "120"))
STALE_TIMEOUT_S: float = float(os.getenv("STALE_DRONE_TIMEOUT_S", "15"))
STALE_CHECK_INTERVAL_S: float = 5.0


class DroneRegistry:
    """
    Singleton registry for all drone agents.

    _drones: Dict[str, MAVSDKDroneAgent]
        Keyed by drone_id - O(1) access, no list scans.

    _semaphore: asyncio.Semaphore
        Shared across all agents to cap concurrent MAVSDK connections.

    _stale_checker_task: asyncio.Task
        Runs every 5 s; marks drones OFFLINE if last_seen > STALE_TIMEOUT_S.
    """

    def __init__(self) -> None:
        self._drones: Dict[str, MAVSDKDroneAgent] = {}
        self._semaphore: asyncio.Semaphore = asyncio.Semaphore(MAX_CONCURRENT_CONNECTIONS)
        self._stale_checker_task: Optional[asyncio.Task] = None
        self._shutdown_event: asyncio.Event = asyncio.Event()

    # --------------------------------------------------------------------------
    # Lifecycle
    # --------------------------------------------------------------------------

    def start(self) -> None:
        """Start background stale-drone checker. Call once from app startup."""
        self._stale_checker_task = asyncio.create_task(
            self._run_stale_checker(), name="stale_checker"
        )
        logger.info(
            "DroneRegistry started (max_connections=%d, stale_timeout=%ss).",
            MAX_CONCURRENT_CONNECTIONS,
            STALE_TIMEOUT_S,
        )

    async def shutdown(self) -> None:
        """
        Graceful shutdown (R10):
          1. Signal shutdown.
          2. RTL any in-flight drones.
          3. Cancel stale checker.
          4. Disconnect all drones.
        """
        logger.info("DroneRegistry shutdown initiated ...")
        self._shutdown_event.set()

        if self._stale_checker_task and not self._stale_checker_task.done():
            self._stale_checker_task.cancel()
            try:
                await self._stale_checker_task
            except (asyncio.CancelledError, Exception):
                pass

        # RTL any drones currently in-flight before disconnecting
        in_flight_ids = [
            drone_id
            for drone_id, agent in self._drones.items()
            if agent.state.status in ("IN_FLIGHT", "RETURNING_HOME", "LANDING")
        ]
        if in_flight_ids:
            logger.warning(
                "Shutdown: RTL triggered for %d in-flight drones: %s",
                len(in_flight_ids),
                in_flight_ids,
            )
            await asyncio.gather(
                *(self._drones[did].emergency_rtl() for did in in_flight_ids),
                return_exceptions=True,
            )

        # Disconnect everything
        await asyncio.gather(
            *(agent.disconnect() for agent in self._drones.values()),
            return_exceptions=True,
        )
        logger.info("DroneRegistry shutdown complete.")

    # --------------------------------------------------------------------------
    # Drone CRUD
    # --------------------------------------------------------------------------

    async def add_drone(self, drone_id: str, connection_string: str) -> MAVSDKDroneAgent:
        """
        Create a new agent, connect it (blocking until GPS-healthy or timeout),
        and add to registry.  Raises on connection failure.
        """
        if drone_id in self._drones:
            existing = self._drones[drone_id]
            if existing.state.is_online:
                logger.info("[%s] Already connected - returning existing agent.", drone_id)
                return existing
            # Reconnect path: clean up stale agent first
            logger.info("[%s] Reconnecting stale agent ...", drone_id)
            await self._safe_disconnect(existing)

        agent = MAVSDKDroneAgent(
            drone_id=drone_id,
            connection_string=connection_string,
            semaphore=self._semaphore,
        )
        # Add to registry before connecting so that stale checker can see it
        self._drones[drone_id] = agent
        try:
            await agent.connect()
        except Exception:
            # Remove from registry if connection fails so re-connect is clean
            self._drones.pop(drone_id, None)
            raise

        logger.info("[%s] Added to registry.", drone_id)
        return agent

    async def remove_drone(self, drone_id: str) -> None:
        """Disconnect and remove a drone from the registry."""
        agent = self._drones.pop(drone_id, None)
        if agent is None:
            return
        await self._safe_disconnect(agent)
        logger.info("[%s] Removed from registry.", drone_id)

    def get_drone(self, drone_id: str) -> MAVSDKDroneAgent:
        """
        O(1) lookup by drone_id.  Raises KeyError (mapped to 404 in FastAPI)
        if not found.
        """
        agent = self._drones.get(drone_id)
        if agent is None:
            raise KeyError(f"Drone '{drone_id}' not found in registry.")
        return agent

    def get_all_states(self) -> List[dict]:
        """
        Return serialisable state snapshots for all registered drones.
        Reads from the DroneState cache only - never queries MAVSDK.  O(n).
        """
        return [agent.get_state_snapshot() for agent in self._drones.values()]

    def get_all_states_dict(self) -> Dict[str, dict]:
        """
        Return serialisable state snapshots for all registered drones keyed by drone_id.
        Reads from the DroneState cache only - never queries MAVSDK.  O(n).
        """
        return {agent.drone_id: agent.get_state_snapshot() for agent in self._drones.values()}

    def get_all_agents(self) -> Dict[str, MAVSDKDroneAgent]:
        """Return a shallow copy of the drone registry dict."""
        return dict(self._drones)

    # --------------------------------------------------------------------------
    # Batch operations (new admin endpoints)
    # --------------------------------------------------------------------------

    async def connect_batch(
        self, entries: List[dict]
    ) -> List[dict]:
        """
        Connect up to N drones concurrently using asyncio.gather.
        Respects the MAX_CONCURRENT_CONNECTIONS semaphore.
        Returns a list of result dicts: {drone_id, success, error}.
        """

        async def _connect_one(drone_id: str, connection_string: str) -> dict:
            try:
                await self.add_drone(drone_id, connection_string)
                return {"drone_id": drone_id, "success": True, "error": None}
            except Exception as exc:
                logger.error("[%s] Batch connect failed: %s", drone_id, exc)
                return {"drone_id": drone_id, "success": False, "error": str(exc)}

        results = await asyncio.gather(
            *(_connect_one(e["drone_id"], e["connection_string"]) for e in entries),
            return_exceptions=False,  # exceptions are caught inside _connect_one
        )
        return list(results)

    async def disconnect_all(self) -> int:
        """
        Gracefully disconnect every drone.
        RTLs any in-flight ones first, then disconnects all.
        Returns the count disconnected.
        """
        count = len(self._drones)
        in_flight = [
            agent
            for agent in self._drones.values()
            if agent.state.status in ("IN_FLIGHT", "RETURNING_HOME", "LANDING")
        ]
        if in_flight:
            await asyncio.gather(
                *(agent.emergency_rtl() for agent in in_flight),
                return_exceptions=True,
            )
        await asyncio.gather(
            *(agent.disconnect() for agent in self._drones.values()),
            return_exceptions=True,
        )
        self._drones.clear()
        logger.info("disconnect_all: %d drones disconnected.", count)
        return count

    # --------------------------------------------------------------------------
    # Spatial queries (placeholder - future R-tree / geohash index)
    # --------------------------------------------------------------------------

    def get_nearby_drones(
        self,
        lat: float,
        lon: float,
        radius_m: float,
    ) -> List[MAVSDKDroneAgent]:
        """
        Return all online drones within radius_m metres of (lat, lon).

        Currently implemented as a linear scan (O(n)) - acceptable for <= 120
        drones on a single event loop.

        TODO: Replace with an R-tree (e.g. rtree / shapely) or geohash index
              once fleet size exceeds ~500 drones and proximity queries become
              a hot path for the AI coordinator.

        Approximation: 1 degree latitude ~ 111,000 m; longitude scale is
        multiplied by cos(lat) for accuracy.
        """
        import math

        nearby: List[MAVSDKDroneAgent] = []
        lat_deg_per_m = 1.0 / 111_000.0
        lon_deg_per_m = 1.0 / (111_000.0 * math.cos(math.radians(lat)))
        radius_lat = radius_m * lat_deg_per_m
        radius_lon = radius_m * lon_deg_per_m

        for agent in self._drones.values():
            if not agent.state.is_online:
                continue
            d_lat = agent.state.lat - lat
            d_lon = agent.state.lon - lon
            # Fast bounding-box pre-filter before full distance calculation
            if abs(d_lat) > radius_lat or abs(d_lon) > radius_lon:
                continue
            dist_m = math.sqrt(
                (d_lat / lat_deg_per_m) ** 2 + (d_lon / lon_deg_per_m) ** 2
            )
            if dist_m <= radius_m:
                nearby.append(agent)

        return nearby

    # --------------------------------------------------------------------------
    # Stale drone detection (R6)
    # --------------------------------------------------------------------------

    async def _run_stale_checker(self) -> None:
        """
        Background loop: every 5 s, mark drones OFFLINE if last_seen > 15 s.
        Drones stay in the registry - they are not removed.
        """
        logger.info("Stale drone checker started.")
        try:
            while not self._shutdown_event.is_set():
                await asyncio.sleep(STALE_CHECK_INTERVAL_S)
                await self.check_stale_drones()
        except asyncio.CancelledError:
            logger.info("Stale drone checker cancelled.")

    async def check_stale_drones(self) -> None:
        """Mark drones OFFLINE if their last_seen is older than STALE_TIMEOUT_S."""
        cutoff = datetime.utcnow() - timedelta(seconds=STALE_TIMEOUT_S)
        for drone_id, agent in self._drones.items():
            state = agent.state
            if state.is_online and state.last_seen < cutoff:
                logger.warning(
                    "[%s] Stale - last seen %s s ago; marking OFFLINE.",
                    drone_id,
                    (datetime.utcnow() - state.last_seen).total_seconds(),
                )
                state.is_online = False
                state.status = "OFFLINE"

    # --------------------------------------------------------------------------
    # Helpers
    # --------------------------------------------------------------------------

    async def _safe_disconnect(self, agent: MAVSDKDroneAgent) -> None:
        """Disconnect without raising."""
        try:
            await agent.disconnect()
        except Exception as exc:
            logger.warning(
                "[%s] Error during safe disconnect: %s", agent.drone_id, exc
            )
