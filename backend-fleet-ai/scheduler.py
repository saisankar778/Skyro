"""
scheduler.py — Fleet AI Drone Assignment Engine (Redesigned).

Implements a 7-factor, 100-point composite scoring system to select the
best available drone for a delivery order.

Eligibility filter (applied before scoring — drones excluded entirely):
  - Status is not IDLE
  - Battery < 25%
  - wind_speed_ms >= 8.0
  - signal_quality_percent < 40.0
  - Redis drone_state:{drone_id} == COOLDOWN

Scoring factors (100 pts total):
  1. Distance        — 25 pts  (normalized, closest wins)
  2. Battery         — 25 pts  (tiered)
  3. Deliveries today— 15 pts  (normalized, fewest wins)
  4. Wind speed      — 15 pts  (tiered)
  5. Signal quality  — 10 pts  (tiered)
  6. Cooldown elapsed— 10 pts  (time since last landing)
  7. Flight time     —  0 pts  (informational only, logged)

Public API:
    get_scheduler() -> DroneScheduler
    NoEligibleDroneError (exception)
"""
from __future__ import annotations

import asyncio
import math
import os
import time
from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Tuple

import structlog

from models import AssignDroneRequest, AssignDroneResponse, DroneScoreBreakdown, DroneState

log = structlog.get_logger(__name__)

CRUISE_SPEED_MPS: float = float(os.getenv("CRUISE_SPEED_MPS", "5.0"))

# Priority → collision priority mapping
_PRIORITY_MAP = {5: 3, 4: 2, 3: 1, 2: 1, 1: 1}  # 5=MEDICAL, 4=EXPRESS, 1-3=STANDARD


class NoEligibleDroneError(Exception):
    """Raised when no drone passes the eligibility filter."""
    pass


# ---------------------------------------------------------------------------
# Geometry helpers
# ---------------------------------------------------------------------------

def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle distance in kilometres."""
    R = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (
        math.sin(dlat / 2) ** 2
        + math.cos(math.radians(lat1))
        * math.cos(math.radians(lat2))
        * math.sin(dlon / 2) ** 2
    )
    return R * 2 * math.asin(math.sqrt(max(0.0, a)))


def eta_seconds(drone: DroneState, dest_lat: float, dest_lon: float) -> int:
    """ETA in seconds with 10% safety margin."""
    dist_km = haversine_km(drone.lat, drone.lon, dest_lat, dest_lon)
    return int((dist_km * 1000 / max(CRUISE_SPEED_MPS, 0.1)) * 1.1)


# ---------------------------------------------------------------------------
# Scoring helpers
# ---------------------------------------------------------------------------

def _score_battery(battery_pct: float) -> float:
    """25-point battery tier score."""
    if battery_pct >= 80:
        return 25.0
    elif battery_pct >= 60:
        return 20.0
    elif battery_pct >= 40:
        return 12.0
    elif battery_pct >= 25:
        return 4.0
    return 0.0


def _score_wind(wind_ms: float) -> float:
    """15-point wind speed tier score."""
    if wind_ms <= 3.0:
        return 15.0
    elif wind_ms <= 6.0:
        return 10.0
    elif wind_ms < 8.0:
        return 4.0
    return 0.0


def _score_signal(signal_pct: float) -> float:
    """10-point signal quality tier score."""
    if signal_pct >= 80:
        return 10.0
    elif signal_pct >= 60:
        return 7.0
    elif signal_pct >= 40:
        return 3.0
    return 0.0


def _score_cooldown(last_landed_at: Optional[float]) -> float:
    """
    10-point cooldown elapsed score.
    Returns the score and a boolean: True means drone is in active cooldown
    (< 60s) and should be excluded.
    """
    if last_landed_at is None:
        return 10.0  # Never landed → no cooldown penalty
    elapsed = time.time() - last_landed_at
    if elapsed > 300:   # > 5 min
        return 10.0
    elif elapsed > 180:  # 3–5 min
        return 6.0
    elif elapsed > 60:   # 1–3 min
        return 2.0
    else:
        return -1.0  # Signal: < 1 min, should set COOLDOWN and exclude


# ---------------------------------------------------------------------------
# Redis telemetry reading
# ---------------------------------------------------------------------------

async def _read_redis_drone_data(drone_id: str) -> dict:
    """Read combined Redis telemetry + state for a drone. Returns {} on failure."""
    result: dict = {}
    try:
        from redis_client import get_redis
        r = await get_redis()
        telemetry = await r.hgetall(f"telemetry:{drone_id}")
        result.update(telemetry or {})
        state_val = await r.get(f"drone_state:{drone_id}")
        if state_val:
            result["drone_state"] = state_val
        deliveries_val = await r.get(f"deliveries_today:{drone_id}")
        if deliveries_val is not None:
            result["deliveries_today"] = deliveries_val
        flight_val = await r.get(f"flight_minutes_today:{drone_id}")
        if flight_val is not None:
            result["flight_minutes_today"] = flight_val
        last_landed_val = await r.get(f"last_landed_at:{drone_id}")
        if last_landed_val is not None:
            result["last_landed_at"] = last_landed_val
    except Exception as exc:
        log.warning(
            "scheduler_redis_read_error",
            event="scheduler_redis_read_error",
            service="fleet-ai",
            drone_id=drone_id,
            error=str(exc),
        )
    return result


async def _set_drone_cooldown(drone_id: str, remaining_seconds: int) -> None:
    """Set drone into COOLDOWN state in Redis for remaining_seconds."""
    try:
        from redis_client import get_redis
        r = await get_redis()
        await r.set(f"drone_state:{drone_id}", "COOLDOWN", ex=max(1, remaining_seconds))
        log.info(
            "drone_cooldown_set",
            event="drone_cooldown_set",
            service="fleet-ai",
            drone_id=drone_id,
            remaining_s=remaining_seconds,
        )
    except Exception as exc:
        log.warning(
            "scheduler_cooldown_set_error",
            event="scheduler_cooldown_set_error",
            service="fleet-ai",
            drone_id=drone_id,
            error=str(exc),
        )


# ---------------------------------------------------------------------------
# Scoring strategy (abstract + default implementation)
# ---------------------------------------------------------------------------

class ScoreStrategy(ABC):
    @abstractmethod
    async def score_async(
        self,
        drone: DroneState,
        redis_data: dict,
        dest_lat: float,
        dest_lon: float,
        priority: int,
        max_deliveries_in_pool: int,
        max_dist_km_in_pool: float,
    ) -> Optional[DroneScoreBreakdown]:
        """
        Return DroneScoreBreakdown or None if drone should be excluded.
        Returning None means this drone is ineligible.
        """


class CompositeScorer(ScoreStrategy):
    """
    Default 100-point weighted scorer implementing all 7 factors.
    """

    async def score_async(
        self,
        drone: DroneState,
        redis_data: dict,
        dest_lat: float,
        dest_lon: float,
        priority: int,
        max_deliveries_in_pool: int,
        max_dist_km_in_pool: float,
    ) -> Optional[DroneScoreBreakdown]:

        drone_id = drone.droneId or drone.drone_id or "unknown"

        # ── Factor 1: Distance (25 pts) ──────────────────────────────────────
        dist_km = haversine_km(drone.lat, drone.lon, dest_lat, dest_lon)
        if max_dist_km_in_pool > 0:
            distance_pts = 25.0 * (1.0 - dist_km / max_dist_km_in_pool)
        else:
            distance_pts = 25.0

        # ── Factor 2: Battery (25 pts) ───────────────────────────────────────
        battery_pts = _score_battery(drone.battery)

        # ── Factor 3: Deliveries today (15 pts) ─────────────────────────────
        try:
            deliveries_today = int(redis_data.get("deliveries_today", 0) or 0)
        except (ValueError, TypeError):
            deliveries_today = 0

        if max_deliveries_in_pool > 0:
            deliveries_pts = 15.0 * (1.0 - deliveries_today / max_deliveries_in_pool)
        else:
            deliveries_pts = 15.0

        # ── Factor 4: Wind speed (15 pts) ────────────────────────────────────
        wind_raw = redis_data.get("wind_speed_ms")
        if wind_raw is not None:
            try:
                wind_ms = float(wind_raw)
                wind_pts = _score_wind(wind_ms)
            except (ValueError, TypeError):
                wind_ms = 0.0
                wind_pts = 7.0  # missing → middle score
        else:
            wind_ms = drone.wind_speed_ms
            wind_pts = 7.0 if wind_ms == 0.0 else _score_wind(wind_ms)

        # ── Factor 5: Signal quality (10 pts) ───────────────────────────────
        signal_raw = redis_data.get("signal_quality_percent")
        if signal_raw is not None:
            try:
                signal_pct = float(signal_raw)
                signal_pts = _score_signal(signal_pct)
            except (ValueError, TypeError):
                signal_pct = 100.0
                signal_pts = 5.0  # missing → middle score
        else:
            signal_pct = drone.signal_quality_percent
            signal_pts = 5.0 if signal_pct == 100.0 else _score_signal(signal_pct)

        # ── Factor 6: Cooldown elapsed (10 pts) ─────────────────────────────
        last_landed_raw = redis_data.get("last_landed_at") or (
            str(drone.last_landed_at) if drone.last_landed_at else None
        )
        last_landed_at: Optional[float] = None
        if last_landed_raw:
            try:
                last_landed_at = float(last_landed_raw)
            except (ValueError, TypeError):
                last_landed_at = None

        cooldown_raw = _score_cooldown(last_landed_at)
        if cooldown_raw < 0:
            # < 1 min since landing: push into COOLDOWN
            elapsed = time.time() - last_landed_at  # type: ignore[arg-type]
            remaining = max(1, int(60 - elapsed))
            await _set_drone_cooldown(drone_id, remaining)
            # Emit WS event (lazy import to avoid circular dep at module load)
            try:
                from main import fleet_ws_manager, _make_ws_event
                cooldown_until = time.time() + remaining
                await fleet_ws_manager.broadcast_json(
                    _make_ws_event(
                        "drone_cooldown_started",
                        drone_id=drone_id,
                        data={"cooldown_until": cooldown_until},
                    )
                )
            except Exception:
                pass
            return None  # Exclude this drone
        cooldown_pts = cooldown_raw

        # ── Factor 7: Flight time today (0 pts — informational) ─────────────
        try:
            flight_minutes_today = float(redis_data.get("flight_minutes_today", 0) or 0)
        except (ValueError, TypeError):
            flight_minutes_today = 0.0

        # ── Total ─────────────────────────────────────────────────────────────
        total = distance_pts + battery_pts + deliveries_pts + wind_pts + signal_pts + cooldown_pts

        breakdown = DroneScoreBreakdown(
            distance_pts=round(distance_pts, 2),
            battery_pts=round(battery_pts, 2),
            deliveries_pts=round(deliveries_pts, 2),
            wind_pts=round(wind_pts, 2),
            signal_pts=round(signal_pts, 2),
            cooldown_pts=round(cooldown_pts, 2),
            total=round(total, 2),
            flight_minutes_today=round(flight_minutes_today, 1),
            distance_km=round(dist_km, 3),
            battery_pct=drone.battery,
        )

        log.debug(
            "drone_score_computed",
            event="drone_score_computed",
            service="fleet-ai",
            drone_id=drone_id,
            **breakdown.dict(),
        )

        return breakdown


# ---------------------------------------------------------------------------
# DroneScheduler
# ---------------------------------------------------------------------------

class DroneScheduler:
    """
    Fleet AI drone assignment engine.

    Uses a pluggable ScoreStrategy (default: CompositeScorer).
    Primary entry point is assign_async() — fully async, reads Redis.
    assign() is a legacy sync wrapper for backward compatibility.
    """

    def __init__(self, scorer: Optional[ScoreStrategy] = None) -> None:
        self._scorer: ScoreStrategy = scorer or CompositeScorer()

    def swap_scorer(self, scorer: ScoreStrategy) -> None:
        """Hot-swap scoring strategy (e.g. for ML model integration)."""
        self._scorer = scorer
        log.info(
            "scorer_swapped",
            event="scorer_swapped",
            service="fleet-ai",
            scorer=type(scorer).__name__,
        )

    async def assign_async(
        self,
        request: AssignDroneRequest,
        drone_states: Optional[Dict[str, DroneState]] = None,
        home_pad_available_only: bool = False,
    ) -> Tuple[str, DroneScoreBreakdown]:
        """
        Select the best drone for the given order.

        Args:
            request: Order assignment request with destination and priority.
            drone_states: Optional pre-loaded drone states (fetched from state_manager if None).
            home_pad_available_only: If True, only consider drones that have an available home pad
                                      (used in fallback path when primary assignment's pad is taken).

        Returns:
            (drone_id, DroneScoreBreakdown) for the selected drone.

        Raises:
            NoEligibleDroneError: If no drone passes eligibility or no states available.
        """
        # Get drone states
        if drone_states is None:
            from state_manager import get_all_states
            drone_states = await get_all_states()

        if not drone_states:
            raise NoEligibleDroneError("No drones registered in state manager.")

        # Resolve destination coordinates from location cache
        from location_cache import resolve_location_coords
        try:
            dest_lat, dest_lon = await resolve_location_coords(request.destination)
        except (KeyError, RuntimeError) as exc:
            raise NoEligibleDroneError(
                f"Cannot resolve delivery location '{request.destination}': {exc}"
            ) from exc

        # Fetch Redis connection and home locations to check locks
        from redis_client import get_redis
        from location_cache import get_home_locations
        r = await get_redis()
        try:
            home_locs = await get_home_locations()
        except Exception:
            home_locs = []

        pad_occupants = {}
        for loc in home_locs:
            try:
                occ = await r.get(f"home_pad_lock:{loc['name']}")
                pad_occupants[loc["name"]] = occ
            except Exception:
                pad_occupants[loc["name"]] = None

        all_home_reserved = len(home_locs) > 0 and all(occ is not None for occ in pad_occupants.values())
        owner_drones = {occ for occ in pad_occupants.values() if occ is not None}

        # ── Step 1: Eligibility filter ────────────────────────────────────────
        exclusion_counts = {
            "not_idle": 0,
            "low_battery": 0,
            "high_wind": 0,
            "low_signal": 0,
            "cooldown": 0,
            "no_home_pad": 0,
        }

        candidates: List[Tuple[str, DroneState, dict]] = []

        for drone_id, drone in drone_states.items():
            # If all home pads are reserved, only allow drones that currently own one of the pads
            if all_home_reserved and drone_id not in owner_drones:
                exclusion_counts["no_home_pad"] += 1
                continue

            # If fallback is active, only consider drones that either have a pad or there is an open pad
            if home_pad_available_only:
                has_pad = drone_id in owner_drones
                has_free = not all_home_reserved
                if not (has_pad or has_free):
                    exclusion_counts["no_home_pad"] += 1
                    continue

            # Status must be IDLE
            if drone.status != "IDLE":
                exclusion_counts["not_idle"] += 1
                continue

            # Battery threshold
            if drone.battery < 25.0:
                exclusion_counts["low_battery"] += 1
                continue

            # Read Redis data for this drone
            redis_data = await _read_redis_drone_data(drone_id)

            # COOLDOWN check in Redis
            if redis_data.get("drone_state") == "COOLDOWN":
                exclusion_counts["cooldown"] += 1
                continue

            # Wind speed check
            wind_raw = redis_data.get("wind_speed_ms")
            wind_ms = 0.0
            if wind_raw is not None:
                try:
                    wind_ms = float(wind_raw)
                except (ValueError, TypeError):
                    wind_ms = 0.0
            else:
                wind_ms = drone.wind_speed_ms

            if wind_ms >= 8.0:
                exclusion_counts["high_wind"] += 1
                continue

            # Signal quality check
            signal_raw = redis_data.get("signal_quality_percent")
            signal_pct = 100.0
            if signal_raw is not None:
                try:
                    signal_pct = float(signal_raw)
                except (ValueError, TypeError):
                    signal_pct = 100.0
            else:
                signal_pct = drone.signal_quality_percent

            if signal_pct < 40.0:
                exclusion_counts["low_signal"] += 1
                continue

            candidates.append((drone_id, drone, redis_data))

        if not candidates:
            msg = (
                f"No eligible drone found for order '{request.orderId}'. "
                f"Exclusions: not_idle={exclusion_counts['not_idle']}, "
                f"low_battery={exclusion_counts['low_battery']}, "
                f"high_wind={exclusion_counts['high_wind']}, "
                f"low_signal={exclusion_counts['low_signal']}, "
                f"cooldown={exclusion_counts['cooldown']}."
            )
            log.warning(
                "no_eligible_drone",
                event="no_eligible_drone",
                service="fleet-ai",
                order_id=request.orderId,
                **exclusion_counts,
            )
            raise NoEligibleDroneError(msg)

        # ── Step 2: Compute pool-wide normalization values ────────────────────
        max_dist_km = max(
            haversine_km(drone.lat, drone.lon, dest_lat, dest_lon)
            for _, drone, _ in candidates
        )
        max_deliveries = max(
            int(rd.get("deliveries_today", 0) or 0) for _, _, rd in candidates
        )
        if max_deliveries == 0:
            max_deliveries = 1  # avoid division by zero

        # ── Step 3: Score each candidate ──────────────────────────────────────
        scored: List[Tuple[str, DroneScoreBreakdown, DroneState]] = []

        for drone_id, drone, redis_data in candidates:
            breakdown = await self._scorer.score_async(
                drone=drone,
                redis_data=redis_data,
                dest_lat=dest_lat,
                dest_lon=dest_lon,
                priority=request.priority,
                max_deliveries_in_pool=max_deliveries,
                max_dist_km_in_pool=max_dist_km,
            )
            if breakdown is None:
                # Drone was excluded during scoring (e.g. entered COOLDOWN)
                continue
            scored.append((drone_id, breakdown, drone))

        if not scored:
            raise NoEligibleDroneError(
                f"All candidates were excluded during scoring for order '{request.orderId}'."
            )

        # ── Step 4: Select winner (highest total; tiebreak: higher battery) ───
        scored.sort(key=lambda x: (x[1].total, x[2].battery), reverse=True)
        winner_id, winner_breakdown, winner_drone = scored[0]

        log.info(
            "drone_selected",
            event="drone_selected",
            service="fleet-ai",
            order_id=request.orderId,
            drone_id=winner_id,
            score=winner_breakdown.total,
            destination=request.destination,
            priority=request.priority,
        )

        return winner_id, winner_breakdown

    def assign(
        self,
        request: AssignDroneRequest,
        drone_states: Dict[str, DroneState],
    ) -> Optional[AssignDroneResponse]:
        """
        Legacy synchronous wrapper — prefer assign_async() for all new code.
        Runs assign_async in the current event loop.
        """
        try:
            loop = asyncio.get_event_loop()
            drone_id, breakdown = loop.run_until_complete(
                self.assign_async(request, drone_states)
            )
            # Find state for ETA calculation
            state = drone_states.get(drone_id)
            if state is None:
                return None
            from location_cache import resolve_location_coords
            dest_lat, dest_lon = loop.run_until_complete(
                resolve_location_coords(request.destination)
            )
            eta = eta_seconds(state, dest_lat, dest_lon)
            confidence = round(min(1.0, breakdown.total / 100.0), 3)
            return AssignDroneResponse(
                droneId=drone_id,
                eta=eta,
                confidence=confidence,
                score=breakdown.total,
                score_breakdown=breakdown,
            )
        except NoEligibleDroneError:
            return None


# ---------------------------------------------------------------------------
# Module singleton
# ---------------------------------------------------------------------------

_scheduler = DroneScheduler()


def get_scheduler() -> DroneScheduler:
    """Return the module-level DroneScheduler singleton."""
    return _scheduler
