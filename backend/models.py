"""
models.py - DroneState dataclass + all Pydantic request/response schemas.

DroneState is a lightweight mutable dataclass updated by background telemetry
tasks. Pydantic models define the REST API contracts; their schemas are frozen
(consumers depend on them).
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict
from pydantic.alias_generators import to_camel


class CamelModel(BaseModel):
    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
    )


# ------------------------------------------------------------------------------
# Telemetry state cache (one per drone, mutated by background asyncio tasks)
# ------------------------------------------------------------------------------

@dataclass
class DroneState:
    """
    Mutable in-memory snapshot of a single drone's telemetry.

    Updated exclusively by the four per-drone background asyncio tasks
    (position, battery, armed, flight-mode).  The WebSocket broadcaster and
    all status endpoints read from this cache; they never query the drone
    directly, which decouples broadcast frequency from telemetry stream rate.
    """
    drone_id: str
    status: str = "IDLE"            # IDLE | CONNECTING | IN_FLIGHT | RETURNING_HOME | LANDING | CHARGING | OFFLINE | FAILED | MAINTENANCE
    battery: float = 0.0            # 0?100 %
    lat: float = 0.0
    lon: float = 0.0
    altitude: float = 0.0           # relative altitude metres
    heading: float = 0.0            # degrees 0?360
    groundspeed: float = 0.0        # m/s
    gps_satellites: int = 0
    armed: bool = False
    mission_id: Optional[str] = None
    last_seen: datetime = field(default_factory=datetime.utcnow)
    is_online: bool = False
    connection_string: str = ""
    flight_mode: str = "UNKNOWN"

    destination: Optional[Dict[str, float]] = None
    home_location: Optional[Dict[str, float]] = None

    def to_dict(self) -> Dict[str, Any]:
        """Serialise to the frozen WebSocket broadcast schema."""
        return {
            "id": self.drone_id,
            "status": self.status,
            "battery": round(self.battery, 1),
            "lat": self.lat,
            "lon": self.lon,
            "altitude": round(self.altitude, 2),
            "heading": round(self.heading, 1),
            "groundspeed": round(self.groundspeed, 2),
            "gps_satellites": self.gps_satellites,
            "armed": self.armed,
            "mission_id": self.mission_id,
            "last_seen": self.last_seen.isoformat() + "Z",
            "is_online": self.is_online,
            "connection_string": self.connection_string,
            "flight_mode": self.flight_mode,
            "mode": self.flight_mode,
            "destination": self.destination,
            "home_location": self.home_location,
            "location": {
                "lat": self.lat,
                "lon": self.lon,
                "alt": self.altitude,
            }
        }


# ------------------------------------------------------------------------------
# Request schemas
# ------------------------------------------------------------------------------

class ConnectRequest(CamelModel):
    drone_id: str
    connection_string: str


class BatchDroneEntry(CamelModel):
    drone_id: str
    connection_string: str


class BatchConnectRequest(CamelModel):
    drones: List[BatchDroneEntry]


class LaunchRequest(CamelModel):
    drone_id: Optional[str] = None
    order_id: str
    delivery_lat: float
    delivery_lon: float
    delivery_alt: float = 20.0


class StatusRequest(CamelModel):
    drone_id: str


class ObstacleAlertRequest(CamelModel):
    drone_id: str
    obstacle_type: str
    distance_m: float


class LandingConfirmRequest(CamelModel):
    drone_id: str
    method: str          # "GPS" | "VISION"
    accuracy_m: float


# ------------------------------------------------------------------------------
# Response schemas
# ------------------------------------------------------------------------------

class ConnectResponse(CamelModel):
    success: bool
    drone_id: str
    status: str
    error: Optional[str] = None


class BatchConnectResult(CamelModel):
    drone_id: str
    success: bool
    error: Optional[str] = None


class BatchConnectResponse(CamelModel):
    results: List[BatchConnectResult]
    connected: int
    failed: int


class LaunchResponse(CamelModel):
    success: bool
    mission_id: str
    drone_id: str


class DroneListEntry(CamelModel):
    id: str
    status: str
    connection_string: str


class DroneListResponse(CamelModel):
    drones: List[DroneListEntry]


class DroneSummaryResponse(CamelModel):
    total: int
    idle: int
    in_flight: int
    returning_home: int
    offline: int
    charging: int
    failed: int


class ObstacleAlertResponse(CamelModel):
    action_taken: str


class LandingConfirmResponse(CamelModel):
    confirmed: bool


class DisconnectAllResponse(CamelModel):
    disconnected: int


class ErrorResponse(CamelModel):
    success: bool = False
    error: str
    code: str
