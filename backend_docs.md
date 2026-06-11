# Skyro Backend Architecture & Algorithms Documentation

## Overview

The Skyro project employs a microservices architecture for its backend to separate concerns, improve scalability, and cleanly handle both regular API traffic and specialized Drone/AI tasks. All services are containerized via Docker and orchestrated using `docker-compose`.

The backend ecosystem consists of three primary services:
1. **`backend` (Drone Controller)**
2. **`backend-orders` (Core API / Database Operations)**
3. **`backend-fleet-ai` (Fleet Management & Intelligence)**

---

## 1. `backend` (Drone Controller)
**Tech Stack:** FastAPI, DroneKit / MAVLink, Docker (Host Network)

**Responsibilities:**
- Acts as the direct bridge to physical or simulated drones (via ArduPilot SITL or physical Pixhawk telemetry).
- Communicates using MAVLink over UDP or Serial connections.
- Exposes REST and WebSocket endpoints for real-time drone telemetry and dispatching commands.
- Runs on port `8080` (locally) and typically requires `network_mode: "host"` on Linux for unhindered UDP packet routing.

**Workflow:**
When a mission is dispatched, this backend directly connects to the drone using a connection string (e.g., `127.0.0.1:14550` or `/dev/ttyUSB0`) and continuously monitors its state, sending status updates back to the Orders API.

---

## 2. `backend-orders` (Core Orders API)
**Tech Stack:** FastAPI, PostgreSQL (asyncpg/psycopg)

**Responsibilities:**
- The primary source of truth for standard business data: Users, Restaurants, Menu Items, and Orders.
- Handles standard CRUD operations.
- Interacts directly with the AWS RDS PostgreSQL database (`DATABASE_URL`).
- Runs on port `8000`.

**Workflow:**
When a user places an order via the frontend, the request hits this service. It saves the order with a `CREATED` status. Once the restaurant accepts, it transitions to `READY_FOR_PICKUP`, triggering the Fleet AI to schedule a drone.

---

## 3. `backend-fleet-ai` (Fleet Management & Intelligence)
**Tech Stack:** FastAPI, PostgreSQL, Redis

**Responsibilities:**
- Oversees the airspace, fleet status, and traffic management.
- Handles complex algorithms for drone assignment, collision avoidance, and landing pad reservations.
- Communicates with `backend` (to send drone commands) and `backend-orders` (to read/update order statuses).
- Runs on port `8002`.

### Core Algorithms in `backend-fleet-ai`

**A. Scheduler & Assignment Algorithm (`scheduler.py`)**
- Evaluates pending orders against available `IDLE` drones.
- Computes an `ai_score` for each drone-order pair based on:
  - Battery levels and estimated flight time (`eta_seconds`).
  - Distance from the drone's current location to the pickup location.
  - Proximity to a valid `HOME` location for post-delivery return.
- Only assigns drones that safely meet all thresholds.

**B. Traffic & Collision Avoidance (`traffic.py`)**
- Constantly predicts future drone positions using physics vectors based on `CRUISE_SPEED_MPS` (e.g., 5.0 m/s).
- Looks ahead by `PREDICT_SECONDS` (e.g., 7 seconds).
- Identifies any drones that breach the `SAFE_THRESHOLD_M` (e.g., 20 meters radius).
- Issues mid-flight reroutes or altitude adjustments to resolve conflicts.

**C. Landing & Pad Reservation (`landing.py` / `authorization.py`)**
- Prevents multiple drones from attempting to land on the same pad or home base simultaneously.
- Uses atomic locks on `home_location_reservations` in the database.
- A drone must secure a reservation lock before transitioning to `RETURNING_HOME`. If no pads are free, the drone will hover or loiter until a slot clears.

---

## Service Interconnection & Workflow

1. **User Action:** Customer places an order on the Frontend.
2. **Order Creation:** `backend-orders` receives the request and stores it in AWS RDS.
3. **Dispatch Trigger:** Once the food is ready, `backend-orders` flags the order.
4. **AI Processing:** `backend-fleet-ai` detects the ready order, runs its scheduling algorithm, and claims an available drone by locking its database record.
5. **Drone Action:** `backend-fleet-ai` commands `backend` to initiate the mission.
6. **Flight:** `backend` sends MAVLink waypoints to the drone. Throughout the flight, `backend-fleet-ai` monitors telemetry via WebSockets and manages traffic to prevent collisions.
7. **Completion:** Drone delivers and returns. `backend-fleet-ai` clears reservations and updates `backend-orders` to mark the order as `DELIVERED`.
