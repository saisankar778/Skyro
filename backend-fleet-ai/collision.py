"""
collision.py — 3D in-flight collision avoidance engine for Fleet AI.

Uses rtree spatial index for fast trajectory bounding-corridor intersection.
Falls back to O(n²) Euclidean midpoint check if rtree/libspatialindex is
not available (e.g. Windows SITL without native library). Logs
collision_engine=fallback_on2 in that case.

Public API:
    get_collision_engine() -> CollisionEngine
    TrajectorySegment (dataclass)
    PRIORITY_MEDICAL, PRIORITY_EXPRESS, PRIORITY_STANDARD
"""
from __future__ import annotations

import asyncio
import math
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

import structlog

log = structlog.get_logger(__name__)

# Priority constants — higher int = higher priority, yields last in conflict resolution
PRIORITY_MEDICAL: int = 3
PRIORITY_EXPRESS: int = 2
PRIORITY_STANDARD: int = 1

# Spatial buffers (metres)
HORIZONTAL_BUFFER_M: float = 8.0
VERTICAL_BUFFER_M: float = 5.0

# Resolution altitude offsets to try, in order
ALT_OFFSETS_M: List[float] = [0.0, 10.0, 20.0, 30.0]

# Metres per degree latitude (approx constant)
M_PER_DEG_LAT: float = 111_320.0


@dataclass
class TrajectorySegment:
    """Represents one drone's planned flight path segment."""

    drone_id: str
    start_lat: float
    start_lon: float
    start_alt: float
    end_lat: float
    end_lon: float
    end_alt: float
    priority: int = PRIORITY_STANDARD
    dispatched_at: float = field(default_factory=time.time)


def _m_per_deg_lon(lat_deg: float) -> float:
    return M_PER_DEG_LAT * math.cos(math.radians(lat_deg))


def _segment_bbox_6d(seg: TrajectorySegment, h_buf: float, v_buf: float) -> Tuple:
    """
    Compute 3D bounding box for rtree (min_x, min_y, min_z, max_x, max_y, max_z).
    Converts lat/lon → approximate metres for uniform units.
    """
    mid_lat = (seg.start_lat + seg.end_lat) / 2
    m_lon = _m_per_deg_lon(mid_lat)

    xs = [seg.start_lat * M_PER_DEG_LAT, seg.end_lat * M_PER_DEG_LAT]
    ys = [seg.start_lon * m_lon,          seg.end_lon * m_lon]
    zs = [seg.start_alt,                   seg.end_alt]

    return (
        min(xs) - h_buf, min(ys) - h_buf, min(zs) - v_buf,
        max(xs) + h_buf, max(ys) + h_buf, max(zs) + v_buf,
    )


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


def _segments_conflict_fallback(
    a: TrajectorySegment, b: TrajectorySegment, a_alt_offset: float = 0.0
) -> bool:
    """
    O(n²) fallback conflict check via midpoint distance.
    Candidate segment 'a' is evaluated with an altitude offset applied.
    """
    a_mid_lat = (a.start_lat + a.end_lat) / 2
    a_mid_lon = (a.start_lon + a.end_lon) / 2
    a_mid_alt = (a.start_alt + a.end_alt) / 2 + a_alt_offset

    b_mid_lat = (b.start_lat + b.end_lat) / 2
    b_mid_lon = (b.start_lon + b.end_lon) / 2
    b_mid_alt = (b.start_alt + b.end_alt) / 2

    horiz_m = _haversine_m(a_mid_lat, a_mid_lon, b_mid_lat, b_mid_lon)
    vert_m = abs(a_mid_alt - b_mid_alt)

    return horiz_m < HORIZONTAL_BUFFER_M and vert_m < VERTICAL_BUFFER_M


class CollisionEngine:
    """
    3D trajectory collision avoidance.

    R-tree mode (preferred): O(log n) conflict queries using spatial index.
    Fallback mode: O(n²) midpoint distance check — safe but slower.
    """

    def __init__(self) -> None:
        self._segments: Dict[str, TrajectorySegment] = {}
        self.fallback: bool = False
        self._index = None
        self._id_map: Dict[str, int] = {}
        self._next_id: int = 1

        try:
            import rtree.index as rtree_index  # type: ignore[import]

            p = rtree_index.Property()
            p.dimension = 3
            self._index = rtree_index.Index(properties=p)
            log.info(
                "collision_engine_initialized",
                event="collision_engine_initialized",
                service="fleet-ai",
                mode="rtree_3d",
            )
        except ImportError:
            self.fallback = True
            log.warning(
                "collision_engine_initialized",
                event="collision_engine_initialized",
                service="fleet-ai",
                mode="fallback_on2",
                collision_engine="fallback_on2",
                reason="rtree/libspatialindex not installed",
            )

    def register_trajectory(self, seg: TrajectorySegment) -> None:
        """Register or replace a drone's active trajectory segment."""
        self.deregister_trajectory(seg.drone_id)
        self._segments[seg.drone_id] = seg

        if not self.fallback and self._index is not None:
            rid = self._next_id
            self._next_id += 1
            self._id_map[seg.drone_id] = rid
            bbox = _segment_bbox_6d(seg, HORIZONTAL_BUFFER_M, VERTICAL_BUFFER_M)
            self._index.insert(rid, bbox)

    def deregister_trajectory(self, drone_id: str) -> None:
        """Remove a drone's trajectory from the index."""
        seg = self._segments.pop(drone_id, None)
        if seg is None:
            return
        if not self.fallback and self._index is not None and drone_id in self._id_map:
            rid = self._id_map.pop(drone_id)
            bbox = _segment_bbox_6d(seg, HORIZONTAL_BUFFER_M, VERTICAL_BUFFER_M)
            try:
                self._index.delete(rid, bbox)
            except Exception as exc:
                log.warning(
                    "collision_rtree_delete_error",
                    event="collision_rtree_delete_error",
                    service="fleet-ai",
                    drone_id=drone_id,
                    error=str(exc),
                )

    def check_and_resolve(
        self,
        candidate: TrajectorySegment,
        all_active: Optional[List[TrajectorySegment]] = None,
    ) -> Tuple[float, bool]:
        """
        Check candidate trajectory for conflicts with higher-priority trajectories.

        Returns:
            (alt_offset_m, should_loiter)
            (0.0, False)  → no conflict
            (n, False)    → resolved by flying n metres higher
            (0.0, True)   → all offsets failed, loiter required
        """
        if all_active is None:
            all_active = list(self._segments.values())

        # Only yield to drones that have higher priority or were dispatched earlier at same priority
        others = [
            s for s in all_active
            if s.drone_id != candidate.drone_id and (
                s.priority > candidate.priority
                or (s.priority == candidate.priority and s.dispatched_at < candidate.dispatched_at)
            )
        ]

        if not others:
            return (0.0, False)

        for offset in ALT_OFFSETS_M:
            if not self._has_conflict_with_offset(candidate, others, offset):
                if offset > 0.0:
                    log.info(
                        "collision_resolved_altitude_offset",
                        event="collision_resolved_altitude_offset",
                        service="fleet-ai",
                        drone_id=candidate.drone_id,
                        alt_offset_m=offset,
                    )
                return (float(offset), False)

        # All offsets conflicted
        log.warning(
            "collision_all_offsets_failed_loiter",
            event="collision_all_offsets_failed_loiter",
            service="fleet-ai",
            drone_id=candidate.drone_id,
        )
        return (0.0, True)

    def _has_conflict_with_offset(
        self,
        candidate: TrajectorySegment,
        others: List[TrajectorySegment],
        alt_offset: float,
    ) -> bool:
        if self.fallback or self._index is None:
            return any(_segments_conflict_fallback(candidate, o, alt_offset) for o in others)

        # Build an offset copy of the candidate for bbox query
        offset_seg = TrajectorySegment(
            drone_id=candidate.drone_id,
            start_lat=candidate.start_lat,
            start_lon=candidate.start_lon,
            start_alt=candidate.start_alt + alt_offset,
            end_lat=candidate.end_lat,
            end_lon=candidate.end_lon,
            end_alt=candidate.end_alt + alt_offset,
            priority=candidate.priority,
            dispatched_at=candidate.dispatched_at,
        )
        bbox = _segment_bbox_6d(offset_seg, HORIZONTAL_BUFFER_M, VERTICAL_BUFFER_M)
        other_ids = {self._id_map[o.drone_id] for o in others if o.drone_id in self._id_map}
        if not other_ids:
            return False
        intersecting = set(self._index.intersection(bbox))
        return bool(intersecting & other_ids)

    def rebuild_from_active(self, active_states: dict) -> None:
        """
        Rebuild trajectory index from active IN_FLIGHT drone states.
        Called on startup to restore collision state from Redis telemetry.
        """
        count = 0
        for drone_id, state in active_states.items():
            if isinstance(state, dict):
                status = state.get("status", "IDLE")
                lat = state.get("lat", 0.0)
                lon = state.get("lon", 0.0)
                alt = state.get("alt", 20.0)
            else:
                status = getattr(state, "status", "IDLE")
                lat = getattr(state, "lat", 0.0)
                lon = getattr(state, "lon", 0.0)
                alt = getattr(state, "alt", 20.0)

            if status != "IN_FLIGHT":
                continue
            if lat == 0.0 and lon == 0.0:
                continue

            seg = TrajectorySegment(
                drone_id=drone_id,
                start_lat=lat, start_lon=lon, start_alt=alt,
                end_lat=lat, end_lon=lon, end_alt=alt,
                priority=PRIORITY_STANDARD,
                dispatched_at=time.time(),
            )
            self.register_trajectory(seg)
            count += 1

        log.info(
            "collision_engine_rebuilt",
            event="collision_engine_rebuilt",
            service="fleet-ai",
            active_flight_count=count,
            mode="fallback_on2" if self.fallback else "rtree_3d",
        )


# Module-level singleton
_collision_engine: Optional[CollisionEngine] = None


def get_collision_engine() -> CollisionEngine:
    """Return module-level CollisionEngine singleton."""
    global _collision_engine
    if _collision_engine is None:
        _collision_engine = CollisionEngine()
    return _collision_engine
