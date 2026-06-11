"""
mission_executor.py - MissionExecutor

Encapsulates the full delivery mission sequence, decoupled from the HTTP layer.
Each mission runs as an asyncio.Task stored on the MAVSDKDroneAgent.

Mission sequence:
  1. Arm + takeoff to TAKEOFF_ALTITUDE_M
  2. fly to delivery coordinates
  3. Land at delivery block
  4. Release payload (set_actuator)
  5. Wait 5 s for payload settle
  6. POST Fleet AI /reserve-home-location
  7. Re-arm + takeoff
  8. Fly to assigned home pad
  9. Land
  10. POST Fleet AI /release-home-location
  11. PATCH orders service -> Delivered

All inter-service HTTP calls use the shared httpx.AsyncClient (R9).

Error handling (R7):
  * ActionError on arm -> retry 3? with 2 s delay
  * Connection errors during mission -> attempt RTL
  * Fleet AI reservation failure -> fallback to HOME_1
  * Orders PATCH failure -> retry 3? with exponential back-off,
    then push to retry_queue for background re-processing
  * Any unhandled exception -> log traceback, mark FAILED, RTL, release reservations
"""

from __future__ import annotations

import asyncio
import logging
import os
import time
import traceback
import uuid
from datetime import datetime
from typing import Optional, Tuple

import httpx

logger = logging.getLogger("mission_executor")

# ------------------------------------------------------------------------------
# Environment knobs
# ------------------------------------------------------------------------------
FLEET_AI_URL: str = os.getenv("FLEET_AI_URL", "https://01ee-115-241-193-69.ngrok-free.app")
ORDERS_API_URL: str = os.getenv("ORDERS_API_URL", os.getenv("ORDERS_API_BASE", "https://fff8-2401-4900-cbd5-7c0d-d549-241c-a989-4b7a.ngrok-free.app"))
PAYLOAD_SETTLE_S: float = 5.0
TAKEOFF_ALTITUDE_M: float = float(os.getenv("TAKEOFF_ALTITUDE_M", "20.0"))

# Fallback home if Fleet AI is unreachable
HOME_1_LAT: float = 16.462795
HOME_1_LON: float = 80.507355

# Named Delivery Block GPS Coordinates
BLOCK_COORDINATES = {
    "SR_Block": {"lat": 16.462635294684286, "lon": 80.50647168669644},
    "C_Block": {"lat": 16.461646855350896, "lon": 80.50569336570064},
    "Admin_Block": {"lat": 16.464874583335895, "lon": 80.50791898212552},
    "Yamuna_Hostel": {"lat": 16.466254271237375, "lon": 80.50757917761362},
    "V_and_G_Hostels": {"lat": 16.463886777402795, "lon": 80.50665800799868},
}

def get_block_name(lat: float, lon: float) -> str:
    """Find the closest named campus block based on GPS coordinates."""
    best_block = "SR_Block"
    min_dist = float("inf")
    for name, coords in BLOCK_COORDINATES.items():
        dist = (lat - coords["lat"])**2 + (lon - coords["lon"])**2
        if dist < min_dist:
            min_dist = dist
            best_block = name
    return best_block


class MissionExecutor:
    """
    Stateless helper that executes delivery missions.

    Receives the shared httpx.AsyncClient and an asyncio.Queue for failed
    order-status updates at construction time.
    """

    def __init__(
        self,
        http_client: httpx.AsyncClient,
        retry_queue: asyncio.Queue,
    ) -> None:
        self._http = http_client
        self._retry_queue = retry_queue

    async def _reserve_landing(self, drone_id: str, zone: str) -> bool:
        """
        POST Fleet AI /reserve-landing to lock a delivery block.
        Returns True if reservation was successful, False otherwise.
        """
        url = f"{FLEET_AI_URL}/reserve-landing"
        try:
            resp = await self._http.post(url, json={"zone": zone, "droneId": drone_id})
            if resp.is_success:
                logger.info("[%s] Reserved landing zone '%s' in Fleet AI.", drone_id, zone)
                return True
            logger.warning(
                "[%s] Fleet AI landing reserve returned %d: %s",
                drone_id,
                resp.status_code,
                resp.text,
            )
        except Exception as exc:
            logger.warning(
                "[%s] Fleet AI landing reserve failed: %s", drone_id, exc
            )
        return False

    async def _confirm_landing(self, drone_id: str, zone: str) -> None:
        """
        POST Fleet AI /landing/confirm to release the delivery zone.
        """
        url = f"{FLEET_AI_URL}/landing/confirm"
        try:
            resp = await self._http.post(
                url, json={"zone": zone, "droneId": drone_id, "landingMode": "GPS"}
            )
            if resp.is_success:
                logger.info("[%s] Confirmed landing and released zone '%s' in Fleet AI.", drone_id, zone)
            else:
                logger.warning(
                    "[%s] Fleet AI landing confirm returned %d: %s",
                    drone_id,
                    resp.status_code,
                    resp.text,
                )
        except Exception as exc:
            logger.warning("[%s] Fleet AI landing confirm failed: %s", drone_id, exc)

    # --------------------------------------------------------------------------
    # Public entry point
    # --------------------------------------------------------------------------

    async def execute(
        self,
        agent,  # MAVSDKDroneAgent - avoid circular import with string annotation
        order_id: str,
        delivery_lat: float,
        delivery_lon: float,
        delivery_alt: float,
    ) -> None:
        """
        Full mission coroutine.  Intended to be run as asyncio.Task on the agent.
        Catches ALL exceptions and performs cleanup (RTL + status update).
        """
        delivery_block: Optional[str] = None
        reserved_zone: Optional[str] = None
        home_lat: float = HOME_1_LAT
        home_lon: float = HOME_1_LON

        try:
            logger.info(
                "[%s] Mission %s started -> (%.6f, %.6f, %.1f m)",
                agent.drone_id,
                order_id,
                delivery_lat,
                delivery_lon,
                delivery_alt,
            )
            agent.state.mission_id = order_id

            # -- Step 0: Resolve and Reserve delivery block (landing zone) from Fleet AI ------
            delivery_block = get_block_name(delivery_lat, delivery_lon)
            while True:
                landing_reserved = await self._reserve_landing(agent.drone_id, delivery_block)
                if landing_reserved:
                    break
                logger.info(
                    "[%s] Landing zone '%s' is busy/occupied. Waiting 5 seconds for clearance...",
                    agent.drone_id,
                    delivery_block,
                )
                await asyncio.sleep(5.0)

            # -- Step 1: Reserve home pad from Fleet AI -----------------------
            home_lat, home_lon, reserved_zone = await self._reserve_home(agent.drone_id)

            # Assign order coordinates and home location to drone state before arming
            agent.state.destination = {"lat": delivery_lat, "lon": delivery_lon}
            agent.state.home_location = {"lat": home_lat, "lon": home_lon}

            # -- Step 2: Arm + takeoff -----------------------------------------
            mission_start_time = time.monotonic()  # Track for flight time recording
            agent.state.status = "IN_FLIGHT"
            await agent.arm_and_takeoff()

            # -- Step 3: Fly to delivery coordinates --------------------------
            await agent.goto_location(delivery_lat, delivery_lon, delivery_alt)

            # -- Step 4: Land at delivery block -------------------------------
            logger.info("[%s] Shifting mode to LAND.", agent.drone_id)
            agent.state.status = "LANDING"
            await agent.land_and_wait()

            logger.info("[%s] Landed at delivery block. Disarming and settling ...", agent.drone_id)
            await agent.disarm_and_wait(settle_s=5.0)   # 5 s - enough for re-arm pre-checks to clear


            # -- Step 5: Release payload ---------------------------------------
            logger.info("[%s] Activating servo to release package...", agent.drone_id)
            await agent.release_payload()

            # -- Step 6: Payload settle delay ---------------------------------
            await asyncio.sleep(PAYLOAD_SETTLE_S)

            # Notify orders service immediately that delivery is complete
            logger.info("[%s] Package dropped. Notifying orders service of delivery.", agent.drone_id)
            await self._notify_delivered(order_id)

            # Record delivery counter in Fleet AI (best-effort)
            await self._record_delivery(agent.drone_id)

            # -- Step 7: Re-arm + takeoff --------------------------------------
            agent.state.status = "IN_FLIGHT"
            # Set destination to home location for the return flight
            agent.state.destination = {"lat": home_lat, "lon": home_lon}
            await agent.arm_and_takeoff()

            # Release landing zone lock in Fleet AI
            if delivery_block:
                await self._confirm_landing(agent.drone_id, delivery_block)
                delivery_block = None

            # -- Step 8: Fly home ----------------------------------------------
            agent.state.status = "RETURNING_HOME"
            await agent.goto_location(home_lat, home_lon, TAKEOFF_ALTITUDE_M)

            # -- Step 8b: Yaw to North (0°) before home pad touchdown ----------
            await agent.yaw_north()

            # -- Step 9: Land at home ------------------------------------------
            logger.info("[%s] Shifting mode to LAND.", agent.drone_id)
            agent.state.status = "LANDING"
            await agent.land_and_wait()

            logger.info("[%s] Landed at home pad. Disarming ...", agent.drone_id)
            await agent.disarm_and_wait(settle_s=3.0)

            # -- Step 10: Notify Fleet AI of confirmed home landing ------------
            # This sets a persistent Redis lock (no TTL) and starts cooldown tracking
            if reserved_zone:
                await self._notify_home_landing(
                    agent.drone_id, reserved_zone, velocity=0.0, altitude=0.0
                )

            # -- Step 11: Record flight time in Fleet AI -----------------------
            flight_minutes = (time.monotonic() - mission_start_time) / 60.0
            await self._record_flight_time(agent.drone_id, flight_minutes)

            agent.state.status = "IDLE"
            agent.state.mission_id = None
            agent.state.destination = None
            agent.state.home_location = None
            logger.info("[%s] Mission %s completed successfully.", agent.drone_id, order_id)

        except asyncio.CancelledError:
            logger.warning("[%s] Mission %s cancelled.", agent.drone_id, order_id)
            await self._handle_mission_failure(
                agent, order_id, reserved_zone, delivery_block, "Mission cancelled"
            )
            raise

        except Exception as exc:
            logger.error(
                "[%s] Mission %s FAILED: %s\n%s",
                agent.drone_id,
                order_id,
                exc,
                traceback.format_exc(),
            )
            await self._handle_mission_failure(
                agent, order_id, reserved_zone, delivery_block, str(exc)
            )

    # --------------------------------------------------------------------------
    # Inter-service calls
    # --------------------------------------------------------------------------

    async def _notify_delivered(self, order_id: str) -> None:
        """
        PATCH orders service to mark order Delivered.
        Retries 3? with exponential back-off.  On final failure, pushes to
        retry_queue for background processing.
        """
        url = f"{ORDERS_API_URL}/api/orders/{order_id}"
        payload = {"status": "Delivered"}

        for attempt in range(1, 4):
            try:
                resp = await self._http.patch(url, json=payload)
                if resp.is_success:
                    logger.info("Order %s marked Delivered.", order_id)
                    return
                logger.warning(
                    "Orders PATCH attempt %d returned %d: %s",
                    attempt,
                    resp.status_code,
                    resp.text,
                )
            except Exception as exc:
                logger.warning(
                    "Orders PATCH attempt %d failed: %s", attempt, exc
                )
            if attempt < 3:
                await asyncio.sleep(2 ** attempt)  # 2 s, 4 s

        # All retries exhausted -> push to retry queue
        logger.error(
            "All 3 PATCH retries failed for order %s - queuing for retry.", order_id
        )
        await self._retry_queue.put({"order_id": order_id, "payload": payload, "url": url})

    async def _record_delivery(self, drone_id: str) -> None:
        """POST Fleet AI /record-delivery. Best-effort — never raises."""
        url = f"{FLEET_AI_URL}/record-delivery"
        try:
            resp = await self._http.post(url, json={"droneId": drone_id})
            if resp.is_success:
                logger.info("[%s] Delivery counter incremented in Fleet AI.", drone_id)
            else:
                logger.warning("[%s] Fleet AI record-delivery returned %d.", drone_id, resp.status_code)
        except Exception as exc:
            logger.warning("[%s] Fleet AI record-delivery failed: %s", drone_id, exc)

    async def _record_flight_time(self, drone_id: str, minutes: float) -> None:
        """POST Fleet AI /record-flight-time. Best-effort — never raises."""
        url = f"{FLEET_AI_URL}/record-flight-time"
        try:
            resp = await self._http.post(url, json={"droneId": drone_id, "minutes": round(minutes, 2)})
            if resp.is_success:
                logger.info("[%s] Flight time %.1f min recorded in Fleet AI.", drone_id, minutes)
            else:
                logger.warning("[%s] Fleet AI record-flight-time returned %d.", drone_id, resp.status_code)
        except Exception as exc:
            logger.warning("[%s] Fleet AI record-flight-time failed: %s", drone_id, exc)

    async def _notify_home_landing(
        self, drone_id: str, pad_id: str, velocity: float, altitude: float
    ) -> None:
        """POST Fleet AI /on-home-landing. Best-effort — never raises."""
        url = f"{FLEET_AI_URL}/on-home-landing"
        try:
            resp = await self._http.post(
                url,
                json={
                    "droneId":  drone_id,
                    "pad_id":   pad_id,
                    "velocity": velocity,
                    "altitude": altitude,
                },
            )
            if resp.is_success:
                logger.info(
                    "[%s] Home landing confirmed in Fleet AI for pad '%s'.", drone_id, pad_id
                )
            else:
                logger.warning(
                    "[%s] Fleet AI on-home-landing returned %d: %s",
                    drone_id, resp.status_code, resp.text,
                )
        except Exception as exc:
            logger.warning("[%s] Fleet AI on-home-landing failed: %s", drone_id, exc)

    async def _reserve_home(
        self, drone_id: str
    ) -> Tuple[float, float, Optional[str]]:
        """
        POST Fleet AI /reserve-home-location.
        Returns (lat, lon, zone).  Falls back to HOME_1 on failure.
        """
        url = f"{FLEET_AI_URL}/reserve-home-location"
        try:
            resp = await self._http.post(url, json={"droneId": drone_id})
            if resp.is_success:
                data = resp.json()
                lat = data.get("lat", HOME_1_LAT)
                lon = data.get("lon", HOME_1_LON)
                zone = data.get("zone")
                logger.info(
                    "[%s] Reserved home zone '%s' at (%.6f, %.6f).", drone_id, zone, lat, lon
                )
                return lat, lon, zone
            logger.warning(
                "[%s] Fleet AI reserve returned %d: %s - using HOME_1 fallback.",
                drone_id,
                resp.status_code,
                resp.text,
            )
        except Exception as exc:
            logger.warning(
                "[%s] Fleet AI reserve failed: %s - using HOME_1 fallback.", drone_id, exc
            )
        return HOME_1_LAT, HOME_1_LON, None

    async def _release_home(self, drone_id: str, zone: str) -> None:
        """
        POST Fleet AI /release-home-location.  Best-effort - never raises.
        """
        url = f"{FLEET_AI_URL}/release-home-location"
        try:
            resp = await self._http.post(
                url, json={"droneId": drone_id, "zone": zone}
            )
            if resp.is_success:
                logger.info("[%s] Released home zone '%s'.", drone_id, zone)
            else:
                logger.warning(
                    "[%s] Fleet AI release returned %d: %s",
                    drone_id,
                    resp.status_code,
                    resp.text,
                )
        except Exception as exc:
            logger.warning("[%s] Fleet AI release failed: %s", drone_id, exc)

    async def _notify_failed(self, order_id: str) -> None:
        """PATCH orders service to mark order as Failed.  Best-effort."""
        url = f"{ORDERS_API_URL}/api/orders/{order_id}"
        try:
            resp = await self._http.patch(url, json={"status": "Failed"})
            if not resp.is_success:
                logger.warning(
                    "Orders PATCH (failed) returned %d: %s", resp.status_code, resp.text
                )
        except Exception as exc:
            logger.warning("Could not notify orders service of failure: %s", exc)

    # --------------------------------------------------------------------------
    # AI Coordinator hook (future integration point)
    # --------------------------------------------------------------------------

    async def receive_override_command(self, agent, command: dict) -> None:
        """
        Future hook for the AI Coordinator to inject real-time overrides into
        a running mission.

        The coordinator calls this method with a command dict such as:
            {"action": "rtl"}
            {"action": "hold"}
            {"action": "set_speed", "speed_mps": 3.0}
            {"action": "reroute", "lat": 16.462, "lon": 80.506, "alt": 20.0}

        Currently implemented actions:
            rtl       - cancel mission task and trigger emergency RTL
            hold      - not yet supported at MAVSDK level (logged, noop)
            set_speed - update cruise speed on the fly (best-effort)

        This method is intentionally non-blocking (async) and never raises.
        All AI_COORDINATOR_URL wiring happens in main.py; this method is
        purely the execution side.
        """
        action = command.get("action", "").lower()
        logger.info(
            "[%s] Coordinator override received: %s", agent.drone_id, command
        )

        if action == "rtl":
            logger.warning(
                "[%s] Coordinator commanded RTL - cancelling mission.", agent.drone_id
            )
            if agent.mission_task and not agent.mission_task.done():
                agent.mission_task.cancel()
            await agent.emergency_rtl()

        elif action == "hold":
            # TODO: implement MAVSDK hold/loiter when coordinator integration lands
            logger.warning(
                "[%s] Coordinator 'hold' not yet implemented - drone will continue.",
                agent.drone_id,
            )

        elif action == "set_speed":
            speed = float(command.get("speed_mps", 5.0))
            try:
                await agent.system.action.set_current_speed(speed)
                logger.info(
                    "[%s] Coordinator set cruise speed to %.1f m/s.", agent.drone_id, speed
                )
            except Exception as exc:
                logger.warning(
                    "[%s] set_speed override failed: %s", agent.drone_id, exc
                )

        elif action == "reroute":
            # TODO: implement mid-mission reroute when path-planning integration lands
            logger.warning(
                "[%s] Coordinator 'reroute' not yet implemented - drone will continue "
                "to original destination.",
                agent.drone_id,
            )

        else:
            logger.warning(
                "[%s] Coordinator sent unknown action '%s' - ignored.",
                agent.drone_id,
                action,
            )

    # --------------------------------------------------------------------------
    # Failure handler
    # --------------------------------------------------------------------------

    async def _handle_mission_failure(
        self,
        agent,
        order_id: str,
        reserved_zone: Optional[str],
        delivery_block: Optional[str],
        error: str,
    ) -> None:
        """
        Called when a mission raises an unhandled exception:
          1. Mark drone FAILED.
          2. Attempt RTL.
          3. Release any Fleet AI reservation.
          4. PATCH orders service -> Failed.
        Never raises.
        """
        agent.state.status = "FAILED"
        agent.state.mission_id = None
        agent.state.destination = None
        agent.state.home_location = None

        # Attempt RTL
        try:
            await agent.emergency_rtl()
        except Exception as rtl_exc:
            logger.critical(
                "[%s] RTL also failed during mission cleanup: %s",
                agent.drone_id,
                rtl_exc,
            )
            agent.state.status = "MAINTENANCE"

        # Retain home pad reservation (do not release on failure)
        pass

        # Confirm/release landing zone if reserved
        if delivery_block:
            await self._confirm_landing(agent.drone_id, delivery_block)

        # Notify orders service
        await self._notify_failed(order_id)
