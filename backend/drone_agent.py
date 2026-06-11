"""
drone_agent.py — MAVSDKDroneAgent

Manages a single physical drone's lifecycle:
  • Connection (via shared semaphore to cap concurrent MAVSDK connections)
  • Four persistent background telemetry tasks (position, battery, armed, flight-mode)
  • Delivery mission as an isolated asyncio.Task with full error recovery
  • Emergency RTL
  • Graceful disconnection

Design principles (100-drone scale):
  R1  — Zero synchronous blocking; every await yields to the event loop.
  R2  — Connection guarded by a shared asyncio.Semaphore(MAX_CONCURRENT_CONNECTIONS).
  R3  — Four telemetry tasks per drone; a crash in one does not affect others.
  R4  — All reads go through DroneState cache; broadcast never touches MAVSDK.
  R7  — Mission task exceptions are caught, logged, and trigger RTL + cleanup.
"""

from __future__ import annotations

import sys

import asyncio
import logging
import math
import os
import traceback
import uuid
from datetime import datetime
from typing import List, Optional

from mavsdk import System
from mavsdk.action import ActionError
from mavsdk.telemetry import FlightMode

from models import DroneState

logger = logging.getLogger("drone_agent")

if sys.version_info >= (3, 11):
    from asyncio import timeout as asyncio_timeout
else:
    from async_timeout import timeout as asyncio_timeout

# ──────────────────────────────────────────────────────────────────────────────
# Environment knobs
# ──────────────────────────────────────────────────────────────────────────────
TAKEOFF_ALTITUDE_M: float = float(os.getenv("TAKEOFF_ALTITUDE_M", "20.0"))
CAMPUS_ELEVATION_AMSL_M: float = float(os.getenv("CAMPUS_ELEVATION_AMSL_M", "25.0"))
MISSION_CRUISE_SPEED_MPS: float = float(os.getenv("MISSION_CRUISE_SPEED_MPS", "5.0"))
CONNECTION_TIMEOUT_S: float = 60.0
GPS_HEALTH_TIMEOUT_S: float = 60.0

# Fallback home location if Fleet AI is unreachable
HOME_1_LAT: float = 16.462795
HOME_1_LON: float = 80.507355

_allocated_ports = set()


def get_free_port() -> int:
    import socket
    while True:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.bind(("", 0))
        port = s.getsockname()[1]
        s.close()
        if port not in _allocated_ports:
            _allocated_ports.add(port)
            return port


class MAVSDKDroneAgent:
    """
    Manages one physical drone. Owns the MAVSDK System object, the mutable
    DroneState cache, four background telemetry tasks, and the current mission
    task (if any).

    Thread-safety: all public methods are async; they run on the single
    asyncio event loop. DroneState fields are mutated only by telemetry tasks
    (which run on the same loop), so no locking is needed.
    """

    def __init__(
        self,
        drone_id: str,
        connection_string: str,
        semaphore: asyncio.Semaphore,
    ) -> None:
        self.drone_id = drone_id

        # Normalize deprecated udp:// and udp: connection strings to udpin:// to prevent Windows IPv6 dual-stack binding issues
        conn = connection_string.strip()
        if conn.startswith("udp://") or conn.startswith("udp:"):
            addr = conn[6:] if conn.startswith("udp://") else conn[4:]
            addr = addr.lstrip("/")
            if addr.startswith(":"):
                conn = f"udpin://0.0.0.0{addr}"
            else:
                conn = f"udpin://{addr}"
        self._connection_string = conn

        self._semaphore = semaphore

        self._grpc_port = get_free_port()
        self.system: System = System(port=self._grpc_port)
        self.state: DroneState = DroneState(
            drone_id=drone_id,
            connection_string=self._connection_string,
        )

        self.mission_task: Optional[asyncio.Task] = None
        self._telemetry_tasks: List[asyncio.Task] = []

    # ──────────────────────────────────────────────────────────────────────────
    # Connection management
    # ──────────────────────────────────────────────────────────────────────────

    async def connect(self) -> None:
        """
        Connect to the drone, wait for GPS health.  Guarded by the shared
        semaphore (R2).  Raises ConnectionError on timeout or GPS failure.
        """
        self.state.status = "CONNECTING"
        logger.info("[%s] Acquiring connection semaphore …", self.drone_id)

        try:
            async with asyncio_timeout(30.0):
                await self._semaphore.acquire()
        except asyncio.TimeoutError:
            self.state.status = "FAILED"
            raise ConnectionError(
                f"[{self.drone_id}] Semaphore acquisition timed out after 30 s — "
                f"too many concurrent connections."
            )

        try:
            logger.info("[%s] Connecting to %s …", self.drone_id, self._connection_string)
            await self.system.connect(system_address=self._connection_string)

            # Wait for MAVLink heartbeat
            try:
                async with asyncio_timeout(CONNECTION_TIMEOUT_S):
                    async for conn_state in self.system.core.connection_state():
                        if conn_state.is_connected:
                            logger.info("[%s] MAVLink heartbeat received.", self.drone_id)
                            break
            except asyncio.TimeoutError:
                raise ConnectionError(
                    f"[{self.drone_id}] No MAVLink heartbeat within {CONNECTION_TIMEOUT_S} s."
                )

            # Wait for GPS health
            try:
                async with asyncio_timeout(GPS_HEALTH_TIMEOUT_S):
                    async for health in self.system.telemetry.health():
                        if health.is_global_position_ok and health.is_home_position_ok:
                            logger.info("[%s] GPS health OK.", self.drone_id)
                            break
            except asyncio.TimeoutError:
                raise ConnectionError(
                    f"[{self.drone_id}] GPS lock not acquired within {GPS_HEALTH_TIMEOUT_S} s."
                )

        except Exception:
            self._semaphore.release()
            self.state.status = "FAILED"
            raise

        self.state.is_online = True
        self.state.status = "IDLE"
        self.state.last_seen = datetime.utcnow()
        logger.info("[%s] Connected and healthy.", self.drone_id)

        await self.start_telemetry_streams()

    async def disconnect(self) -> None:
        """
        Cancel telemetry tasks, abort any running mission, release semaphore.
        """
        logger.info("[%s] Disconnecting …", self.drone_id)
        await self.stop_telemetry_streams()

        if self.mission_task and not self.mission_task.done():
            self.mission_task.cancel()
            try:
                await self.mission_task
            except (asyncio.CancelledError, Exception):
                pass

        self.state.is_online = False
        self.state.status = "OFFLINE"
        try:
            self._semaphore.release()
        except ValueError:
            pass  # Already released (e.g., connection failed before acquire completed)

        if self._grpc_port in _allocated_ports:
            _allocated_ports.remove(self._grpc_port)

        if hasattr(self, "system") and self.system:
            try:
                self.system._stop_mavsdk_server()
                logger.info("[%s] Explicitly stopped mavsdk_server process.", self.drone_id)
            except Exception as exc:
                logger.warning("[%s] Error stopping mavsdk_server: %s", self.drone_id, exc)

        logger.info("[%s] Disconnected.", self.drone_id)

    # ──────────────────────────────────────────────────────────────────────────
    # Telemetry streams (R3 — each in its own isolated asyncio.Task)
    # ──────────────────────────────────────────────────────────────────────────

    async def start_telemetry_streams(self) -> None:
        """Launch the four background telemetry tasks."""
        self._telemetry_tasks = [
            asyncio.create_task(
                self._task_telemetry_position(), name=f"{self.drone_id}:position"
            ),
            asyncio.create_task(
                self._task_telemetry_battery(), name=f"{self.drone_id}:battery"
            ),
            asyncio.create_task(
                self._task_telemetry_armed(), name=f"{self.drone_id}:armed"
            ),
            asyncio.create_task(
                self._task_telemetry_flight_mode(), name=f"{self.drone_id}:flight_mode"
            ),
        ]
        for t in self._telemetry_tasks:
            t.add_done_callback(self._on_telemetry_task_done)
        logger.info("[%s] Telemetry tasks started.", self.drone_id)

    async def stop_telemetry_streams(self) -> None:
        """Cancel all telemetry tasks and await their completion."""
        for task in self._telemetry_tasks:
            if not task.done():
                task.cancel()
        results = await asyncio.gather(*self._telemetry_tasks, return_exceptions=True)
        for r in results:
            if isinstance(r, Exception) and not isinstance(r, asyncio.CancelledError):
                logger.warning("[%s] Telemetry task exception on stop: %s", self.drone_id, r)
        self._telemetry_tasks.clear()
        logger.info("[%s] Telemetry tasks stopped.", self.drone_id)

    def _on_telemetry_task_done(self, task: asyncio.Task) -> None:
        """Callback: log unexpected task exits without crashing the app."""
        if task.cancelled():
            return
        exc = task.exception()
        if exc is not None:
            logger.error(
                "[%s] Telemetry task '%s' crashed: %s",
                self.drone_id,
                task.get_name(),
                exc,
                exc_info=True,
            )
            # Mark drone as potentially stale; stale-checker will handle OFFLINE
            # transition.  Do NOT affect other drones.

    async def _task_telemetry_position(self) -> None:
        """Stream position + velocity_ned → update DroneState cache."""
        try:
            async for pos in self.system.telemetry.position():
                self.state.lat = pos.latitude_deg
                self.state.lon = pos.longitude_deg
                self.state.altitude = pos.relative_altitude_m
                self.state.last_seen = datetime.utcnow()
                self.state.is_online = True
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            logger.error("[%s] Position stream error: %s", self.drone_id, exc)

    async def _task_telemetry_battery(self) -> None:
        """Stream battery percentage → update DroneState cache."""
        try:
            async for battery in self.system.telemetry.battery():
                pct = battery.remaining_percent
                # MAVSDK returns 0–1 range; guard against already-scaled values
                self.state.battery = (pct * 100.0) if pct <= 1.0 else pct
                self.state.last_seen = datetime.utcnow()
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            logger.error("[%s] Battery stream error: %s", self.drone_id, exc)

    async def _task_telemetry_armed(self) -> None:
        """Stream armed state + derive groundspeed from velocity_ned."""
        # Run both armed and velocity_ned concurrently within this task
        armed_task = asyncio.create_task(self._stream_armed())
        vel_task = asyncio.create_task(self._stream_velocity())
        try:
            await asyncio.gather(armed_task, vel_task)
        except asyncio.CancelledError:
            armed_task.cancel()
            vel_task.cancel()
            await asyncio.gather(armed_task, vel_task, return_exceptions=True)
            raise

    async def _stream_armed(self) -> None:
        try:
            async for armed in self.system.telemetry.armed():
                self.state.armed = armed
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            logger.error("[%s] Armed stream error: %s", self.drone_id, exc)

    async def _stream_velocity(self) -> None:
        try:
            async for vel in self.system.telemetry.velocity_ned():
                self.state.groundspeed = math.sqrt(
                    vel.north_m_s ** 2 + vel.east_m_s ** 2
                )
                # Derive heading from velocity vector
                heading_rad = math.atan2(vel.east_m_s, vel.north_m_s)
                heading_deg = math.degrees(heading_rad) % 360.0
                self.state.heading = heading_deg
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            logger.error("[%s] Velocity stream error: %s", self.drone_id, exc)

    async def _task_telemetry_flight_mode(self) -> None:
        """Stream flight mode and translate to status string."""
        _FLIGHT_MODE_STATUS_MAP = {
            FlightMode.READY: "IDLE",
            FlightMode.TAKEOFF: "IN_FLIGHT",
            FlightMode.HOLD: "IN_FLIGHT",
            FlightMode.MISSION: "IN_FLIGHT",
            FlightMode.RETURN_TO_LAUNCH: "RETURNING_HOME",
            FlightMode.LAND: "LANDING",
            FlightMode.OFFBOARD: "IN_FLIGHT",
            FlightMode.FOLLOW_ME: "IN_FLIGHT",
            FlightMode.MANUAL: "IDLE",
            FlightMode.ALTCTL: "IN_FLIGHT",
            FlightMode.POSCTL: "IN_FLIGHT",
            FlightMode.ACRO: "IN_FLIGHT",
            FlightMode.STABILIZED: "IN_FLIGHT",
            FlightMode.RATTITUDE: "IN_FLIGHT",
        }
        try:
            async for mode in self.system.telemetry.flight_mode():
                self.state.flight_mode = mode.name
                # Only override status with flight-mode derived value when no
                # mission is actively being tracked (mission_executor controls
                # status during a mission).
                if self.state.mission_id is None:
                    if not self.state.armed:
                        self.state.status = "IDLE"
                    else:
                        self.state.status = _FLIGHT_MODE_STATUS_MAP.get(mode, "IDLE")
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            logger.error("[%s] Flight-mode stream error: %s", self.drone_id, exc)

    # ──────────────────────────────────────────────────────────────────────────
    # Mission helpers
    # ──────────────────────────────────────────────────────────────────────────

    async def arm_and_takeoff(self) -> None:
        """
        Arm the drone and climb to TAKEOFF_ALTITUDE_M.

        Waits for READY flight mode before arming (critical for re-arm after
        delivery landing — ArduPilot stays in LAND mode for a few seconds).
        Retries arming up to 5 times with 3 s delay on ActionError.
        """
        try:
            await self.system.action.set_current_speed(MISSION_CRUISE_SPEED_MPS)
        except Exception as e:
            logger.warning("[%s] Failed to set current speed to %.1f: %s", self.drone_id, MISSION_CRUISE_SPEED_MPS, e)

        try:
            await self.system.action.set_takeoff_altitude(TAKEOFF_ALTITUDE_M)
        except Exception as e:
            logger.warning("[%s] Failed to set takeoff altitude to %.1f: %s", self.drone_id, TAKEOFF_ALTITUDE_M, e)

        # ── Wait for flight controller to reach a READY / armable mode ────────
        # After a LAND+disarm cycle the FCU stays in LAND mode briefly.
        # arm() called in LAND mode will always fail the pre-arm checks.
        logger.info("[%s] Waiting for READY flight mode before arming …", self.drone_id)
        READY_MODES = {FlightMode.READY, FlightMode.HOLD, FlightMode.MANUAL, FlightMode.POSCTL}
        try:
            async with asyncio_timeout(15.0):
                async for mode in self.system.telemetry.flight_mode():
                    if mode in READY_MODES:
                        logger.info("[%s] Flight mode is %s — ready to arm.", self.drone_id, mode.name)
                        break
        except asyncio.TimeoutError:
            logger.warning(
                "[%s] Timed out waiting for READY mode — attempting arm anyway.", self.drone_id
            )

        for attempt in range(1, 6):
            try:
                logger.info("[%s] Arming drone (attempt %d/5) …", self.drone_id, attempt)
                await self.system.action.arm()
                logger.info("[%s] Armed successfully on attempt %d.", self.drone_id, attempt)
                break
            except ActionError as e:
                logger.warning(
                    "[%s] Arm attempt %d failed: %s", self.drone_id, attempt, e
                )
                if attempt == 5:
                    raise
                await asyncio.sleep(3.0)

        logger.info("[%s] Initiating takeoff to %.1f m …", self.drone_id, TAKEOFF_ALTITUDE_M)
        await self.system.action.takeoff()

        # Wait until relative altitude ≥ 95 % of target
        target = TAKEOFF_ALTITUDE_M * 0.95
        async for pos in self.system.telemetry.position():
            if pos.relative_altitude_m >= target:
                logger.info("[%s] Takeoff altitude reached (%.1f m).", self.drone_id, pos.relative_altitude_m)
                break

    async def goto_location(self, lat: float, lon: float, relative_alt: float) -> None:
        """
        Fly to (lat, lon) at (CAMPUS_ELEVATION_AMSL_M + relative_alt) AMSL.
        Waits until the drone is within ~5 m of the target.
        """
        amsl = CAMPUS_ELEVATION_AMSL_M + relative_alt
        logger.info(
            "[%s] goto_location → (%.6f, %.6f) AMSL=%.1f m", self.drone_id, lat, lon, amsl
        )
        await self.system.action.goto_location(lat, lon, amsl, float("nan"))

        # Poll position until within ~5 m (≈ 0.000045 degrees per metre)
        THRESHOLD_DEG = 0.000045  # ≈ 5 m
        async for pos in self.system.telemetry.position():
            d_lat = pos.latitude_deg - lat
            d_lon = pos.longitude_deg - lon
            dist = math.sqrt(d_lat ** 2 + d_lon ** 2)
            if dist < THRESHOLD_DEG:
                logger.info("[%s] Arrived at (%.6f, %.6f).", self.drone_id, lat, lon)
                break

    async def yaw_north(self) -> None:
        """
        Command drone to face North (yaw = 0°) before home pad touchdown.

        Reads current position from the telemetry position stream and issues
        goto_location at the same coordinates with yaw_deg=0.0 (North).
        A 2-second settle delay follows to allow the yaw to stabilise before
        land() is called.

        Only used for HOME pad landings — delivery block landings are unaffected.
        """
        logger.info("[%s] Yawing to North (0°) for home pad landing …", self.drone_id)
        try:
            # Read current position from telemetry
            current_pos = None
            async with asyncio_timeout(5.0):
                async for pos in self.system.telemetry.position():
                    current_pos = pos
                    break

            if current_pos is None:
                logger.warning(
                    "[%s] Could not read current position for yaw_north — skipping yaw.",
                    self.drone_id,
                )
                return

            amsl = current_pos.absolute_altitude_m
            lat  = current_pos.latitude_deg
            lon  = current_pos.longitude_deg

            # goto_location fourth parameter is yaw_deg; 0.0 = North
            await self.system.action.goto_location(lat, lon, amsl, 0.0)

            # Allow yaw to settle before descent
            await asyncio.sleep(2.0)
            logger.info("[%s] Yaw to North complete.", self.drone_id)

        except asyncio.TimeoutError:
            logger.warning(
                "[%s] yaw_north timed out reading position — skipping yaw.", self.drone_id
            )
        except Exception as exc:
            logger.warning(
                "[%s] yaw_north failed (%s) — continuing to land without yaw correction.",
                self.drone_id,
                exc,
            )

    async def land_and_wait(self) -> None:
        """Command land and wait until on-ground."""
        logger.info("[%s] Landing …", self.drone_id)
        await self.system.action.land()
        async for in_air in self.system.telemetry.in_air():
            if not in_air:
                logger.info("[%s] Landed.", self.drone_id)
                break

    async def disarm_and_wait(self, settle_s: float = 3.0) -> None:
        """
        Disarm the drone and wait `settle_s` seconds for ArduPilot to clear
        pre-arm safety checks before allowing a subsequent re-arm.
        """
        logger.info("[%s] Disarming …", self.drone_id)
        try:
            await self.system.action.disarm()
        except Exception as exc:
            logger.warning("[%s] Disarm returned error (may already be disarmed): %s", self.drone_id, exc)
        logger.info("[%s] Waiting %.1f s post-disarm for pre-arm checks to clear …", self.drone_id, settle_s)
        await asyncio.sleep(settle_s)

    async def release_payload(self) -> None:
        """Actuate payload release servo (actuator index 1)."""
        logger.info("[%s] Releasing payload …", self.drone_id)
        try:
            await self.system.action.set_actuator(1, 1.0)
            await asyncio.sleep(2.0)
            await self.system.action.set_actuator(1, -1.0)
            logger.info("[%s] Payload released.", self.drone_id)
        except Exception as exc:
            logger.warning(
                "[%s] Payload release set_actuator failed (non-fatal, continuing mission): %s",
                self.drone_id,
                exc
            )

    async def emergency_rtl(self) -> None:
        """Trigger Return-to-Launch. Best-effort — never raises."""
        try:
            logger.warning("[%s] Emergency RTL initiated.", self.drone_id)
            await self.system.action.return_to_launch()
            self.state.status = "RETURNING_HOME"
        except Exception as exc:
            logger.critical(
                "[%s] RTL FAILED — drone may require manual intervention: %s",
                self.drone_id,
                exc,
            )

    # ──────────────────────────────────────────────────────────────────────────
    # State snapshot
    # ──────────────────────────────────────────────────────────────────────────

    def get_state_snapshot(self) -> dict:
        """Return a serialisable dict of the current DroneState (for WS broadcast)."""
        return self.state.to_dict()
