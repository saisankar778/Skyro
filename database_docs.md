# Skyro Database Architecture Documentation

## Overview

The Skyro project uses a robust relational database model hosted on **AWS RDS PostgreSQL** (version 15+). The database serves as the single source of truth for the entire system, synchronizing the state between the Core Orders API, the Fleet AI, and the Drone Controllers.

For local development and continuous integration, a mirrored PostgreSQL container is provided in `docker-compose.yml`, initialized by the scripts inside the `db/` folder.

---

## Schema & Initialization

The database structure is defined in `db/schema.sql`, and dummy/initial data is provided via `db/seed.sql`.

### Core Database Entities

1. **`locations`**
   - The foundational table for mapping coordinates.
   - Types (`location_type` enum): `RESTAURANT`, `DELIVERY_BLOCK`, `HOME`.
   - Used for mapping pickup points, drop-off points, and drone home bases.

2. **`users`**
   - Stores customer credentials, names, and contact details.

3. **`restaurants` & `menu_items`**
   - Stores vendor profiles, ratings, and rich display fields (cuisine, offers, hero images).
   - Menu items are linked via `restaurant_id` and contain pricing and availability states.

4. **`orders` & `order_items`**
   - Captures user transactions.
   - Links to `user_id`, `restaurant_id`, `pickup_location_id`, and `drop_location_id`.
   - Tracks the lifecycle of the delivery using the `order_status` enum (e.g., `CREATED`, `PREPARING`, `READY_FOR_PICKUP`, `IN_FLIGHT`, `DELIVERED`).

5. **`drones`**
   - Represents the physical or simulated drone fleet.
   - Identifies drones via a unique `drone_key` (MAVLink identifier).
   - Tracks real-time `battery_level`, `current_location_id`, and `drone_status` (e.g., `IDLE`, `IN_FLIGHT`, `CHARGING`).

6. **`delivery_missions`**
   - Bridges `orders` and `drones`.
   - Stores the AI Scheduler's output (`ai_score`, `eta_seconds`).
   - Tracks timestamps for mission start and completion.

7. **`home_location_reservations`**
   - **Crucial for safety:** Prevents physical drone collisions at home bases.
   - Drones must place a lock on a `location_id` (where type = `HOME`) before returning.
   - Managed concurrently by the `backend-fleet-ai` service.

8. **`system_events`**
   - An audit log table storing JSONB payloads for system observability and debugging.

---

## Database Enums & State Machines

To ensure data integrity, state transitions are restricted by PostgreSQL ENUMs:

- **`order_status`**: Limits an order's lifecycle strictly from `CREATED` through `DELIVERED` or `FAILED`.
- **`drone_status`**: Limits a drone's state. A drone must be `IDLE` to be selected by the AI scheduler. It transitions to `ASSIGNED`, then `IN_FLIGHT`, and finally `RETURNING_HOME` / `CHARGING`.
- **`mission_status`**: Tracks the granular state of the flight mission independent of the customer-facing order status.

---

## Integration with Services

- **`backend-orders`**: Owns the CRUD operations for Users, Restaurants, and Orders. Reads from and writes to the DB constantly.
- **`backend-fleet-ai`**: Heavily reads `orders` (where status = `READY_FOR_PICKUP`) and `drones` (where status = `IDLE`). Performs atomic locks on `home_location_reservations`.
- **`backend`**: While it primarily handles MAVLink, it can read/write drone telemetry directly to the DB or relay it through `backend-fleet-ai`.

Database migrations and connections utilize `asyncpg` for high-performance asynchronous operations within the FastAPI event loop, ensuring the system can handle concurrent fleet updates and user requests simultaneously.
