"""
Fleet AI — Shared Pydantic Models

All schemas used across Fleet AI modules and exposed in API responses.
"""

from __future__ import annotations

from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field


# ─────────────────────────────────────────────────────────────────────────────
# DRONE STATE
# ─────────────────────────────────────────────────────────────────────────────

class DroneState(BaseModel):
    droneId:      str       = "unknown"
    drone_id:     Optional[str] = None   # alias accepted from WS
    lat:          float = 0.0
    lon:          float = 0.0
    alt:          float = 0.0
    altitude:     float = 0.0            # alias
    battery:      float = 100.0
    status:       str   = "IDLE"         # IDLE | IN_MISSION | RETURNING_HOME | OFFLINE | COOLDOWN
    mode:         str   = "UNKNOWN"
    armed:        bool  = False
    velocity_x:   float = 0.0
    velocity_y:   float = 0.0
    velocity_z:   float = 0.0
    historical_deliveries: float = 0.0
    last_seen:    float = 0.0            # epoch seconds

    # ── New fields (Fleet AI redesign) ────────────────────────────────────────
    wind_speed_ms:          float         = 0.0
    signal_quality_percent: float         = 100.0
    last_landed_at:         Optional[float] = None   # epoch seconds
    deliveries_today:       int           = 0
    flight_minutes_today:   float         = 0.0
    cooldown_until:         Optional[float] = None   # epoch seconds

    class Config:
        populate_by_name = True


# ─────────────────────────────────────────────────────────────────────────────
# LOCATION
# ─────────────────────────────────────────────────────────────────────────────

class LocationOut(BaseModel):
    """Represents a row from the locations table."""
    id:         Optional[str]
    name:       str
    type:       str                 # HOME | DELIVERY_BLOCK | RESTAURANT
    latitude:   float
    longitude:  float
    is_active:  bool = True


# ─────────────────────────────────────────────────────────────────────────────
# DRONE SCORE BREAKDOWN
# ─────────────────────────────────────────────────────────────────────────────

class DroneScoreBreakdown(BaseModel):
    """Per-factor score breakdown for a single candidate drone (out of 100 pts)."""
    distance_pts:    float = 0.0   # 0–25
    battery_pts:     float = 0.0   # 0–25
    deliveries_pts:  float = 0.0   # 0–15
    wind_pts:        float = 0.0   # 0–15
    signal_pts:      float = 0.0   # 0–10
    cooldown_pts:    float = 0.0   # 0–10
    total:           float = 0.0   # 0–100
    # Informational — not scored
    flight_minutes_today: float = 0.0
    distance_km:          float = 0.0
    battery_pct:          float = 0.0


# ─────────────────────────────────────────────────────────────────────────────
# DRONE ASSIGNMENT
# ─────────────────────────────────────────────────────────────────────────────

class AssignDroneRequest(BaseModel):
    orderId:     str
    destination: str               # delivery block name e.g. "SR_Block"
    priority:    int = Field(1, ge=1, le=5)


class AssignDroneResponse(BaseModel):
    droneId:         str
    eta:             int               # seconds
    confidence:      float             # 0-1
    score:           float             # weighted scoring value
    score_breakdown: Optional[DroneScoreBreakdown] = None


# ─────────────────────────────────────────────────────────────────────────────
# LANDING ZONE (DELIVERY BLOCKS — in-flight landing spots)
# ─────────────────────────────────────────────────────────────────────────────

class ReserveLandingRequest(BaseModel):
    zone:    str                   # delivery block name e.g. "SR_Block"
    droneId: str


class LandingConfirmRequest(BaseModel):
    zone:         str
    droneId:      str
    landing_mode: str   = "GPS"   # GPS | VISION
    offset_x:     float = 0.0
    offset_y:     float = 0.0


class LandingZoneStatus(BaseModel):
    zone:       str
    occupied:   bool
    drone:      Optional[str]


# ─────────────────────────────────────────────────────────────────────────────
# HOME LOCATION RESERVATION
# ─────────────────────────────────────────────────────────────────────────────

class HomeLocationRequest(BaseModel):
    droneId: str


class HomeLocationResponse(BaseModel):
    """Returned to a drone after home location is reserved."""
    zone:      str        # e.g. "HOME_1"
    lat:       float
    lon:       float
    reserved:  bool = True


class ReleaseHomeRequest(BaseModel):
    droneId: str
    zone:    str          # e.g. "HOME_1"


# ─────────────────────────────────────────────────────────────────────────────
# HOME LANDING CONFIRMATION (new — post-landing Redis lock)
# ─────────────────────────────────────────────────────────────────────────────

class HomeLandingRequest(BaseModel):
    droneId:  str
    pad_id:   str
    velocity: float = 0.0   # m/s
    altitude: float = 0.0   # metres


# ─────────────────────────────────────────────────────────────────────────────
# FLIGHT TIME / DELIVERY COUNTER (new endpoints)
# ─────────────────────────────────────────────────────────────────────────────

class RecordFlightTimeRequest(BaseModel):
    droneId: str
    minutes: float


class RecordDeliveryRequest(BaseModel):
    droneId: str


class DroneMetricsResponse(BaseModel):
    droneId:              str
    flight_minutes_today: float = 0.0
    deliveries_today:     int   = 0
    cooldown_state:       str   = "IDLE"    # IDLE | COOLDOWN
    last_landed_at:       Optional[float] = None


# ─────────────────────────────────────────────────────────────────────────────
# MISSION AUTHORIZATION
# ─────────────────────────────────────────────────────────────────────────────

class AuthorizeMissionRequest(BaseModel):
    droneId:      str
    orderId:      str
    destination:  str


class AuthorizeMissionResponse(BaseModel):
    decision: str          # APPROVED | DENIED | WAIT
    reason:   str
    details:  dict = {}


# ─────────────────────────────────────────────────────────────────────────────
# AIR TRAFFIC
# ─────────────────────────────────────────────────────────────────────────────

class ConflictPair(BaseModel):
    drone_a:          str
    drone_b:          str
    predicted_dist_m: float
    resolution:       str


class ObstacleAlert(BaseModel):
    droneId:  str
    lat:      float
    lon:      float
    alt:      float
    severity: str = "LOW"         # LOW | MEDIUM | HIGH


# Alias used in traffic.py endpoint
ObstacleAlertRequest = ObstacleAlert


# ─────────────────────────────────────────────────────────────────────────────
# TRAFFIC / CONFLICT RESPONSES
# ─────────────────────────────────────────────────────────────────────────────

class ConflictsResponse(BaseModel):
    conflicts: List[ConflictPair] = []
    safe:      bool = True


# ─────────────────────────────────────────────────────────────────────────────
# FLEET STATUS
# ─────────────────────────────────────────────────────────────────────────────

class FleetStatusResponse(BaseModel):
    drones:       Dict[str, DroneState] = {}
    zones:        List[LandingZoneStatus] = []
    conflicts:    List[ConflictPair] = []
    total_active: int = 0
