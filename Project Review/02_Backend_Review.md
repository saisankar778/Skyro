# SKYRO — Backend Review

> Complete documentation of all three backend microservices: Orders Service, Drone Backend, and Fleet AI.

---

## Architecture Overview

Skyro has **three independent Python FastAPI backends** that communicate via REST and WebSocket:

```
┌─────────────────┐     ┌──────────────────┐     ┌──────────────────────┐
│ backend-orders  │     │ backend (Drone)  │     │ backend-fleet-ai     │
│ Port 8000       │     │ Port 8080        │     │ Port 8002            │
│                 │     │                  │     │                      │
│ Data + Auth +   │◄────│ Drone hardware   │◄────│ AI intelligence      │
│ Payments        │     │ control          │     │ layer                │
└─────────────────┘     └──────────────────┘     └──────────────────────┘
```

**Why three services?**
1. **Separation of concerns** — data operations vs hardware control vs AI logic
2. **Independent scaling** — orders service handles most traffic, can scale horizontally
3. **Safety** — drone hardware code is isolated; a crash in orders doesn't affect flight
4. **Process Isolation** — drone backend runs on Python 3.11 with MAVSDK-Python, fully isolated from other APIs. A crash in orders or fleet-ai does not affect active flight controls.

---

## Service 1: backend-orders (Port 8000)

### Role
Central data service. Everything related to orders, restaurants, menus, locations, users, authentication, and payments flows through here.

### Files

| File | Lines | Purpose |
|------|-------|---------|
| `main.py` | 128 | FastAPI app, route registration, startup/shutdown hooks |
| `database.py` | 264 | Dual-mode DB connection (PostgreSQL asyncpg / SQLite fallback) |
| `crud.py` | 351 | All CRUD operations with frontend↔DB status mapping |
| `schemas.py` | 117 | Pydantic request/response models |
| `auth.py` | 334 | AWS Cognito authentication (OTP + email/password) |
| `payments.py` | 98 | Razorpay payment integration |
| `events.py` | 30 | WebSocket broadcasting for real-time updates |

### API Endpoints

#### Orders
| Method | Endpoint | Purpose |
|--------|----------|---------|
| `POST` | `/api/orders` | Create new order |
| `GET` | `/api/orders` | List all orders (newest first) |
| `GET` | `/api/orders/{id}` | Get single order (by UUID or legacy ORD-xxx ID) |
| `PATCH` | `/api/orders/{id}` | Update order status or drone assignment |
| `POST` | `/api/orders/{id}/assign-drone` | Atomic drone lock (used by Fleet AI) |

#### Restaurants & Menus
| Method | Endpoint | Purpose |
|--------|----------|---------|
| `GET` | `/api/restaurants` | All active restaurants with GPS, rating, image |
| `GET` | `/api/menu-items?restaurant_id=xxx` | Menu items, filterable by restaurant |

#### Locations
| Method | Endpoint | Purpose |
|--------|----------|---------|
| `GET` | `/api/locations?type=HOME` | GPS locations (HOME / RESTAURANT / DELIVERY_BLOCK) |
| `POST` | `/api/locations/home-reservations` | Persist home pad reservation to DB |

#### Authentication (AWS Cognito)
| Method | Endpoint | Purpose |
|--------|----------|---------|
| `POST` | `/api/auth/signup` | Create Cognito user (phone) |
| `POST` | `/api/auth/start` | Initiate OTP flow |
| `POST` | `/api/auth/verify` | Verify OTP code → get JWT tokens |
| `POST` | `/api/auth/email/signup` | Email registration |
| `POST` | `/api/auth/email/confirm` | Email verification code |
| `POST` | `/api/auth/email/login` | Email/password login → JWT tokens |
| `GET` | `/api/auth/me` | Verify token, return user info |

#### Payments (Razorpay)
| Method | Endpoint | Purpose |
|--------|----------|---------|
| `POST` | `/api/payments/razorpay/order` | Create Razorpay order (amount in paise) |
| `POST` | `/api/payments/razorpay/verify` | Verify payment signature (HMAC-SHA256) |

#### WebSocket
| Protocol | Endpoint | Purpose |
|----------|----------|---------|
| `WS` | `/ws` | Real-time broadcast: order_created, order_updated, order_assigned |

### Database Connection (`database.py`)

The most technically interesting file. It auto-detects PostgreSQL vs SQLite:

```python
DATABASE_URL = os.getenv("DATABASE_URL", f"sqlite:///{DB_PATH}")
_is_postgres = DATABASE_URL.startswith("postgresql")
```

**For PostgreSQL:** Creates a custom `_AsyncPGDatabase` class that:
1. Parses the connection URL manually
2. Creates an `asyncpg` connection pool with SSL for AWS RDS
3. Provides `fetch_all()`, `fetch_one()`, `execute()`, `execute_many()` methods
4. Compiles SQLAlchemy queries to raw SQL with `$1, $2` positional params (asyncpg format)

**For SQLite:** Uses the standard `databases` library with `aiosqlite`.

This dual-mode approach means development works without Docker (SQLite) while production uses AWS RDS (PostgreSQL).

### Order Status Mapping (`crud.py`)

The frontend uses human-readable statuses, but PostgreSQL uses enum values:

| Frontend Status | PostgreSQL Enum |
|----------------|----------------|
| Placed | CREATED |
| Accepted | CONFIRMED |
| Cooking | PREPARING |
| Ready for Launch | READY_FOR_PICKUP |
| En Route | IN_FLIGHT |
| Delivered | DELIVERED |
| Failed | FAILED |
| Declined | CANCELLED |

`crud.py` has bidirectional mapping dictionaries (`_DB_STATUS_TO_FRONTEND` and `_FRONTEND_STATUS_TO_DB`) that translate in both directions.

### Atomic Drone Assignment

```python
# Uses SQL UPDATE ... WHERE assigned_drone_id IS NULL
# Only ONE drone can ever be assigned to an order (prevents race conditions)
query = orders.update().where(
    and_(orders.c.id == real_uuid, orders.c.assigned_drone_id == None)
).values(assigned_drone_id=drone_id, status="DRONE_ASSIGNED")
```

---

## Service 2: backend (Port 8080) — Drone Control

### Role
Direct hardware interface to real ArduPilot/Pixhawk drones via MAVSDK-Python and MAVLink protocol. Controls arming, takeoff, navigation, landing, servo payload release, and return-to-home.

### Files

| File | Lines | Purpose |
|------|-------|---------|
| `main.py` | ~580 | FastAPI app, route registrations, startup/shutdown hooks, telemetry task dispatcher |
| `drone_agent.py` | ~400 | MAVSDKDroneAgent: manages telemetry streams, armed/takeoff/landing/RTL, and wraps the MAVSDK System object |
| `mission_executor.py` | ~310 | MissionExecutor: handles the state transitions and execution of a delivery mission inside an isolated async Task |
| `drone_registry.py` | ~270 | DroneRegistry: tracks active drones, implements connection semaphore concurrency guards, and performs spatial proximity checks |
| `ws_manager.py` | ~150 | WebSocketManager: tracks open connections and broadcasts telemetry updates to clients |
| `models.py` | ~110 | DroneState and configuration structures |
| `requirements.txt` | 9 | mavsdk, pymavlink, fastapi, uvicorn[standard], httpx, websockets, pydantic, python-dotenv |

### API Endpoints

| Method | Endpoint | Purpose |
|--------|----------|---------|
| `POST` | `/api/launch` | Start full delivery mission (async task) |
| `POST` | `/api/connect` | Connect to drone via system address string |
| `POST` | `/api/status` | Get single drone status |
| `GET` | `/api/drones` | List all connected drones |
| `GET` | `/api/drones/status` | Full telemetry for all drones (Fleet AI uses this) |
| `GET` | `/api/drones/{id}/status` | Single drone full telemetry |
| `POST` | `/api/obstacle-alert` | Store obstacle flag for mission loop |
| `POST` | `/api/landing/confirm` | Landing confirmation (GPS/VISION mode) |
| `DELETE` | `/api/drones/{id}` | Disconnect drone |
| `WS` | `/ws` | Broadcasts drone telemetry every 2 seconds |

### The MAVSDKDroneAgent Class

The core class that wraps a MAVSDK `System` object, manages telemetry stream tasks, and holds local cache state:

```python
class MAVSDKDroneAgent:
    def __init__(self, drone_id: str, connection_string: str, semaphore: asyncio.Semaphore):
        # Connects to drone via MAVSDK-Python
        # Supports: UDP ("udp://127.0.0.1:14550")
        #           TCP ("tcp://127.0.0.1:5760")
        #           Serial ("serial:///dev/ttyUSB0:57600")
        # Guarded by a shared asyncio.Semaphore (R2) to prevent socket/resource exhaustion.
```

### Complete Mission Flow

**`perform_delivery(drone_id, block_coords)` (implemented in `MissionExecutor`):**

```
1. arm_and_takeoff()
   ├── Set horizontal speed limit via set_maximum_speed(5.0)
   ├── Set takeoff altitude to 20m
   ├── Arm motors (retries up to 3 times with 2s delay on ActionError)
   ├── Call takeoff() to launch
   └── Wait until relative altitude ≥ 95% of 20m

2. goto_location(lat, lon, relative_alt=20)
   ├── Send 3D GPS navigation command using MAVSDK's goto_location()
   ├── Poll position at 1Hz rate
   └── Arrive when Euclidean distance from destination < 0.000045 degrees (~5m)

3. Land at destination
   ├── Call land() via Action API
   └── Poll in_air() telemetry stream until landed flag is False

4. RELEASE PAYLOAD
   ├── Call set_actuator(index=1, value=1.0) to open the servo release gate
   ├── wait 2 seconds
   ├── Call set_actuator(index=1, value=-1.0) to close the servo release gate
   └── wait 5 seconds (payload settle time)

5. RESERVE HOME PAD
   ├── POST /reserve-home-location to Fleet AI
   ├── Get assigned home pad GPS coordinates (e.g. HOME_3)
   └── Fallback to saved home or default HOME_1 if Fleet AI is offline

6. RETURN FLIGHT
   ├── Re-arm motors in GUIDED mode (or action auto-arms)
   ├── Takeoff to 20m
   ├── Navigates to reserved home pad GPS via goto_location()
   └── Arrive when distance < 0.000045 degrees

7. LAND AT HOME
   ├── Call land() via Action API
   └── Poll in_air() telemetry stream until landed flag is False

8. RELEASE HOME PAD
   └── POST /release-home-location to Fleet AI
```

### WebSocket Broadcasting

The `/ws` endpoint sends telemetry for all connected drones every 2 seconds:

```json
{
  "type": "status_update",
  "drones": {
    "D-01": {
      "armed": true,
      "mode": "GUIDED",
      "altitude": 18.5,
      "battery": 92,
      "location": { "lat": 16.4630, "lon": 80.5075, "alt": 18.5 }
    }
  },
  "timestamp": "2026-05-09T12:00:00"
}
```

Also broadcasts: `mission_completed`, `mission_failed`, `arrived_at_block`, `order_delivered`, `obstacle_alert`, `landing_confirmed`.

### Campus Coordinates

| Location | Latitude | Longitude | Type |
|----------|----------|-----------|------|
| SR Block | 16.462635 | 80.506472 | DELIVERY_BLOCK |
| C Block | 16.461647 | 80.505693 | DELIVERY_BLOCK |
| Admin Block | 16.464875 | 80.507919 | DELIVERY_BLOCK |
| Yamuna Hostel | 16.466254 | 80.507579 | DELIVERY_BLOCK |
| V & G Hostels | 16.463887 | 80.506658 | DELIVERY_BLOCK |
| HOME_1 | 16.462795 | 80.507355 | HOME (default) |

---

## Service 3: backend-fleet-ai (Port 8002) — Fleet Intelligence

### Role
The AI brain. Handles drone assignment scoring, air traffic deconfliction, landing zone management, home pad reservations, and mission authorization.

### Files

| File | Lines | Purpose |
|------|-------|---------|
| `main.py` | 281 | FastAPI app, WS manager, fleet status pusher |
| `scheduler.py` | 211 | AI scoring engine for drone assignment |
| `state_manager.py` | 212 | Real-time drone state via WS subscription |
| `landing.py` | 341 | Delivery zones + home pad reservation system |
| `traffic.py` | 233 | Air traffic conflict detection |
| `authorization.py` | 216 | Mission safety gate (4-check system) |
| `models.py` | 171 | All Pydantic models |

### API Endpoints

| Method | Endpoint | Purpose |
|--------|----------|---------|
| `POST` | `/assign-drone` | AI-based best drone selection |
| `POST` | `/authorize-mission` | 4-step safety gate → APPROVED/WAIT/DENIED |
| `POST` | `/reserve-landing` | Lock delivery zone for approach |
| `POST` | `/landing/confirm` | Release delivery zone (GPS/VISION) |
| `GET` | `/zone-status` | All delivery zone occupancy |
| `POST` | `/reserve-home-location` | Reserve free home pad for returning drone |
| `POST` | `/release-home-location` | Release home pad after landing |
| `GET` | `/home-status` | All 5 home pad statuses |
| `GET` | `/conflicts` | Predicted air traffic conflicts |
| `POST` | `/obstacle-alert` | Obstacle detection hook |
| `GET` | `/fleet-status` | Complete fleet snapshot |
| `WS` | `/ws` | Real-time fleet push every 2 seconds |

### AI Drone Assignment (`scheduler.py`)

**Scoring Formula:**
```
score = 0.40 × battery_normalized        (penalize < 20%)
      + 0.30 × (1 / (1 + distance_km))  (closer is better)
      + 0.20 × availability_flag          (1.0 if IDLE, else 0)
      + 0.10 × historical_efficiency      (past deliveries, cap 100)
```

**Exclusion rules:**
- Battery < 15% → excluded
- Distance > 5km → excluded (score = 0)
- Status ≠ IDLE → excluded

**Design:** Uses Strategy pattern (`ScoreStrategy` ABC). The `RuleBasedScorer` can be hot-swapped for an ML model via `scheduler.swap_scorer(your_model)`.

**ETA Calculation:** Haversine distance ÷ cruise speed (5 m/s) × 1.1 safety margin.

### State Manager (`state_manager.py`)

Maintains live drone state by subscribing to the drone backend's WebSocket:

```
Fleet AI ──WS──► backend:8080/ws
                  │
                  ├── Receives "status_update" messages
                  ├── Updates in-memory dict: {drone_id: DroneState}
                  ├── Tracks last_seen timestamps
                  └── Marks drones OFFLINE after 15 seconds of silence
```

**Reconnection:** Exponential backoff (2s → 4.5s → 6.75s → ... → 30s max).

**Fallback:** If WS is down, `poll_drone_status_http()` can fetch via `GET /api/drones/{id}/status`.

### Mission Authorization (`authorization.py`)

**4 Safety Checks (run in order, cheapest first):**

| # | Check | Pass | Fail |
|---|-------|------|------|
| 1 | Drone is IDLE, battery ≥ 15% | Continue | DENIED |
| 2 | Order exists, status valid, assigned to this drone | Continue | DENIED |
| 3 | Landing zone is free | Continue | WAIT (retry) |
| 4 | No predicted air traffic conflicts | Continue | WAIT (retry) |

**Results:**
- `APPROVED` — All checks pass, safe to launch
- `WAIT` — Temporary issue (zone occupied, traffic), retry in a few seconds
- `DENIED` — Hard failure (drone busy, bad order, low battery)

### Air Traffic Detection (`traffic.py`)

**Algorithm:**
1. Get all active drones (status ≠ IDLE/OFFLINE)
2. For each drone, predict position 7 seconds ahead using velocity vectors
3. Check all pairwise distances (haversine 3D)
4. Flag pairs within 20m as conflicts
5. Suggest resolution: altitude separation (+5m) or delayed launch (10s hold)

**Complexity:** O(n²) — handles 100 drones in < 1ms.

### Landing Zone Management (`landing.py`)

**Delivery Zones (in-memory):**
- 5 delivery blocks + 3 legacy aliases
- Lock before approach, release after landing
- Auto-release stale reservations after 5 minutes

**Home Pads (PostgreSQL-backed):**
- 5 physical landing pads (HOME_1 through HOME_5)
- In-memory for fast locking + async DB persistence for durability
- Algorithm: find first unreserved pad, mark reserved, return GPS coordinates

---

## Inter-Service Communication Map

```
Clients (Web / Android) ──REST──► backend-orders (:8000)   [orders, restaurants, auth, payments]
Clients (Web / Android) ──REST──► backend (:8080)           [drone connect/launch/status]
Clients (Web / Android) ──WS────► backend-orders/ws         [order events]
Clients (Web / Android) ──WS────► backend:8080/ws           [drone telemetry]

backend ──REST──► backend-orders                            [PATCH order → Delivered]
backend ──REST──► backend-fleet-ai                          [reserve/release home pad]

fleet-ai ──WS──► backend:8080/ws                            [subscribe to telemetry]
fleet-ai ──REST─► backend-orders                            [fetch locations, persist reservations]
```

### ngrok Tunneling & Mobile App Headers (Development)
When testing the backends locally with the Android application (`Skyro_app`), APIs are exposed via `ngrok` tunnels. Because ngrok intercepts requests with a browser warning page, the Android client's OkHttp engine explicitly injects the following custom header to all REST and WebSocket connections:
*   Header Name: `ngrok-skip-browser-warning`
*   Header Value: `true`

The FastAPI endpoints in both `backend-orders` and `backend` (Drone) handle these incoming requests transparently through standard CORS and JSON content handling.

### Docker Networking

In Docker Compose, services use container names as hostnames:
- `backend-orders` → `http://backend-orders:8000`
- `backend` → `http://backend:8080`
- `redis` → `redis://redis:6379`

---

## Dependencies

### backend (Drone Control)
```
mavsdk, pymavlink, fastapi, uvicorn[standard], httpx,
websockets, pydantic, python-dotenv
```

### backend-orders
```
fastapi, uvicorn[standard], SQLAlchemy, databases[asyncpg], asyncpg,
psycopg2-binary, pydantic, aiosqlite, boto3, python-jose, requests,
razorpay, python-dotenv
```

### backend-fleet-ai
```
fastapi>=0.110, uvicorn[standard]>=0.27, httpx>=0.27, websockets>=12.0,
pydantic>=2.0, asyncpg>=0.29, redis>=5.0, psycopg2-binary>=2.9, boto3>=1.34
```

---

*Document generated: May 2026 | Project: Skyro Drone Delivery System | Campus: SRM University, Amaravati*
