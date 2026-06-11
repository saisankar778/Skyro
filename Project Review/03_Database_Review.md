# SKYRO — Database Review

> Complete documentation of the PostgreSQL database: schema, tables, enums, relationships, seed data, migration, and connection configuration.

---

## 1. Database Overview

| Property | Value |
|----------|-------|
| **Engine** | PostgreSQL 15 (AWS RDS in production) |
| **Database Name** | `skyro` |
| **Admin User** | `skyro_admin` |
| **AWS Region** | `ap-south-1` (Mumbai) |
| **RDS Instance** | `skyro-db.cl4o2c2matz8.ap-south-1.rds.amazonaws.com` |
| **Total Tables** | 11 |
| **Extensions** | `uuid-ossp` (for UUID generation) |
| **Schema File** | `db/schema.sql` (270 lines) |
| **Seed File** | `db/seed.sql` (270 lines) |
| **Migration Script** | `db/migrate.py` (165 lines) |

### Connection Options

| Environment | DATABASE_URL |
|-------------|-------------|
| **Local (no Docker)** | `sqlite:///./orders.db` (automatic fallback) |
| **Local Docker** | `postgresql+asyncpg://skyro_admin:local_dev_pass@localhost:5432/skyro` |
| **AWS RDS** | `postgresql+asyncpg://skyro_admin:<password>@skyro-db.cl4o2c2matz8.ap-south-1.rds.amazonaws.com:5432/skyro?sslmode=require` |

---

## 2. Entity Relationship Diagram

```
                         ┌──────────────┐
                         │   locations   │ ← Central GPS table
                         │──────────────│    (HOME, RESTAURANT,
                         │ id (UUID PK) │     DELIVERY_BLOCK)
                         │ name (unique)│
                         │ type (enum)  │
                         │ lat, lon     │
                         └──────┬───────┘
                                │
            ┌───────────────────┼───────────────────┐
            │                   │                   │
            ▼                   ▼                   ▼
   ┌────────────────┐  ┌──────────────┐  ┌─────────────────────┐
   │  restaurants   │  │    orders    │  │ home_location_      │
   │────────────────│  │──────────────│  │ reservations        │
   │ id (UUID PK)  │  │ id (UUID PK) │  │─────────────────────│
   │ name          │  │ legacy_id    │  │ location_id (PK/FK) │
   │ location_id──►│  │ user_id──────│──►│ is_reserved        │
   │ rating        │  │ restaurant_id│  │ reserved_by_drone   │
   │ cuisine       │  │ pickup_loc──►│  └─────────────────────┘
   │ offer         │  │ drop_loc────►│
   │ image_url     │  │ status(enum) │
   └───────┬───────┘  │ drone_id     │
           │          │ total_amount  │
           ▼          └──────┬───────┘
   ┌────────────────┐        │
   │  menu_items    │        ▼
   │────────────────│  ┌──────────────┐     ┌──────────────┐
   │ id (UUID PK)  │  │ order_items  │     │    users     │
   │ restaurant_id─┤  │──────────────│     │──────────────│
   │ name          │  │ order_id────►│     │ id (UUID PK) │
   │ price         │  │ menu_item_id │     │ name, email  │
   │ category      │  │ item_name    │     │ phone        │
   │ image_url     │  │ quantity     │     │ password_hash│
   └───────────────┘  │ price_at_time│     └──────────────┘
                      └──────────────┘
   ┌────────────────┐     ┌──────────────────┐
   │    drones      │     │ delivery_missions│
   │────────────────│     │──────────────────│
   │ id (UUID PK)  │◄────│ drone_id         │
   │ drone_key     │     │ order_id (unique)│
   │ name, status  │     │ pickup_loc       │
   │ battery_level │     │ drop_loc         │
   │ current_loc   │     │ home_loc         │
   │ last_heartbeat│     │ status (enum)    │
   └───────────────┘     │ ai_score         │
                         │ eta_seconds      │
   ┌────────────────┐    └──────────────────┘
   │ system_events  │
   │────────────────│
   │ entity_type    │
   │ entity_id      │
   │ event_type     │
   │ payload (JSONB)│
   └────────────────┘
```

---

## 3. Enum Types

### `location_type`
```sql
CREATE TYPE location_type AS ENUM ('RESTAURANT', 'DELIVERY_BLOCK', 'HOME');
```

### `order_status`
```sql
CREATE TYPE order_status AS ENUM (
  'CREATED',           -- Order placed by user
  'CONFIRMED',         -- Vendor accepted
  'PREPARING',         -- Vendor is cooking
  'READY_FOR_PICKUP',  -- Food ready, waiting for drone
  'DRONE_ASSIGNED',    -- Fleet AI locked a drone
  'IN_FLIGHT',         -- Drone is flying to destination
  'DELIVERED',         -- Successfully delivered
  'FAILED',            -- Mission failed
  'CANCELLED'          -- Vendor declined or user cancelled
);
```

### `drone_status`
```sql
CREATE TYPE drone_status AS ENUM (
  'IDLE', 'RESERVED', 'ASSIGNED', 'IN_FLIGHT',
  'RETURNING_HOME', 'CHARGING', 'MAINTENANCE'
);
```

### `mission_status`
```sql
CREATE TYPE mission_status AS ENUM (
  'CREATED', 'ASSIGNED', 'IN_PROGRESS', 'DELIVERED',
  'RETURNING_HOME', 'COMPLETED', 'FAILED'
);
```

---

## 4. Table Details

### 4.1 `locations` — Core GPS Table

All physical locations in the system. Shared by all services.

| Column | Type | Constraints |
|--------|------|-------------|
| id | UUID | PK, auto-generated |
| name | VARCHAR(100) | UNIQUE, NOT NULL |
| type | location_type | NOT NULL |
| latitude | DOUBLE PRECISION | NOT NULL |
| longitude | DOUBLE PRECISION | NOT NULL |
| is_active | BOOLEAN | DEFAULT TRUE |
| created_at | TIMESTAMP | DEFAULT now() |

**Seed data:** 5 HOME + 7 RESTAURANT + 5 DELIVERY_BLOCK = **17 locations**

---

### 4.2 `users`

| Column | Type | Constraints |
|--------|------|-------------|
| id | UUID | PK |
| name | VARCHAR(100) | NOT NULL |
| email | VARCHAR(150) | UNIQUE, NOT NULL |
| phone | VARCHAR(15) | |
| password_hash | TEXT | NOT NULL |
| created_at | TIMESTAMP | DEFAULT now() |

---

### 4.3 `restaurants`

| Column | Type | Constraints |
|--------|------|-------------|
| id | UUID | PK |
| name | VARCHAR(100) | NOT NULL |
| tagline | TEXT | |
| rating | DECIMAL(2,1) | DEFAULT 0 |
| location_id | UUID | FK → locations.id, NOT NULL |
| is_active | BOOLEAN | DEFAULT TRUE |
| cuisine | VARCHAR(100) | e.g., "Pizza, Fast Food" |
| delivery_time_min | INT | DEFAULT 20 |
| price_for_two | INT | DEFAULT 300 (₹) |
| offer | TEXT | e.g., "50% OFF" |
| image_url | TEXT | Unsplash URL |

**Seed data:** 7 restaurants (Dominos, US Pizza, Chat & Chill, Paradise, Total Fresh, Baskin Robbins, Nescafe)

---

### 4.4 `menu_items`

| Column | Type | Constraints |
|--------|------|-------------|
| id | UUID | PK |
| restaurant_id | UUID | FK → restaurants.id (CASCADE delete) |
| name | VARCHAR(100) | NOT NULL |
| description | TEXT | |
| price | DECIMAL(10,2) | NOT NULL |
| category | VARCHAR(50) | e.g., "Pizza", "Desserts" |
| image_url | TEXT | Unsplash URL |
| is_available | BOOLEAN | DEFAULT TRUE |

**Seed data:** 35 menu items (5 per restaurant) with real images and descriptions.

---

### 4.5 `orders`

| Column | Type | Constraints |
|--------|------|-------------|
| id | UUID | PK |
| legacy_id | VARCHAR(64) | UNIQUE — "ORD-1712345678901" from frontend |
| user_id | UUID | FK → users.id |
| restaurant_id | UUID | FK → restaurants.id |
| pickup_location_id | UUID | FK → locations.id |
| drop_location_id | UUID | FK → locations.id |
| status | order_status | NOT NULL, DEFAULT 'CREATED' |
| assigned_drone_id | VARCHAR(64) | Fleet AI atomic lock field |
| total_amount | DECIMAL(10,2) | |
| created_at | TIMESTAMP | DEFAULT now() |
| updated_at | TIMESTAMP | |
| completed_at | TIMESTAMP | |

**Key design:** The `assigned_drone_id` field enables atomic drone locking — `UPDATE ... WHERE assigned_drone_id IS NULL` prevents race conditions.

---

### 4.6 `order_items`

| Column | Type | Constraints |
|--------|------|-------------|
| id | UUID | PK |
| order_id | UUID | FK → orders.id (CASCADE delete) |
| menu_item_id | UUID | FK → menu_items.id |
| item_name | VARCHAR(100) | Denormalized for historical accuracy |
| quantity | INT | NOT NULL, CHECK > 0 |
| price_at_time | DECIMAL(10,2) | NOT NULL — price when ordered |

---

### 4.7 `drones`

| Column | Type | Constraints |
|--------|------|-------------|
| id | UUID | PK |
| drone_key | VARCHAR(64) | UNIQUE, NOT NULL — MAVLink identifier |
| name | VARCHAR(50) | |
| status | drone_status | DEFAULT 'IDLE' |
| battery_level | INT | CHECK 0-100 |
| current_location_id | UUID | FK → locations.id |
| last_heartbeat | TIMESTAMP | |
| last_updated | TIMESTAMP | DEFAULT now() |

---

### 4.8 `delivery_missions`

| Column | Type | Constraints |
|--------|------|-------------|
| id | UUID | PK |
| order_id | UUID | UNIQUE FK → orders.id (one mission per order) |
| drone_id | UUID | FK → drones.id |
| pickup_location_id | UUID | FK → locations.id |
| drop_location_id | UUID | FK → locations.id |
| home_location_id | UUID | FK → locations.id |
| status | mission_status | DEFAULT 'CREATED' |
| ai_score | DECIMAL(5,4) | Scheduler confidence score |
| eta_seconds | INT | Estimated flight time |
| started_at | TIMESTAMP | |
| completed_at | TIMESTAMP | |
| created_at | TIMESTAMP | DEFAULT now() |

---

### 4.9 `home_location_reservations`

Critical table for drone return-to-home slot management.

| Column | Type | Constraints |
|--------|------|-------------|
| location_id | UUID | PK, FK → locations.id |
| is_reserved | BOOLEAN | DEFAULT FALSE |
| reserved_by_drone | VARCHAR(64) | drone_key |
| reserved_at | TIMESTAMP | |
| released_at | TIMESTAMP | |

**Trigger:** `trg_check_home_type` ensures only HOME-type locations can be inserted.

---

### 4.10 `system_events` — Audit Log

| Column | Type | Constraints |
|--------|------|-------------|
| id | UUID | PK |
| entity_type | VARCHAR(50) | e.g., "order", "drone", "mission" |
| entity_id | UUID | |
| event_type | VARCHAR(50) | e.g., "status_change", "assignment" |
| payload | JSONB | Flexible event data |
| created_at | TIMESTAMP | DEFAULT now() |

---

## 5. Indexes

```sql
CREATE INDEX idx_orders_status       ON orders(status);
CREATE INDEX idx_orders_created_at   ON orders(created_at DESC);
CREATE INDEX idx_drones_status       ON drones(status);
CREATE INDEX idx_locations_type      ON locations(type);
CREATE INDEX idx_missions_status     ON delivery_missions(status);
CREATE INDEX idx_home_reserved       ON home_location_reservations(is_reserved);
CREATE INDEX idx_system_events_entity ON system_events(entity_type, entity_id);
```

---

## 6. Seed Data Summary

### Locations (17 total)

**5 HOME pads:**
| Name | Latitude | Longitude |
|------|----------|-----------|
| HOME_1 | 16.46279507 | 80.50735460 |
| HOME_2 | 16.46286645 | 80.50755120 |
| HOME_3 | 16.46283558 | 80.50771749 |
| HOME_4 | 16.46285616 | 80.50792671 |
| HOME_5 | 16.46267739 | 80.50761959 |

**7 Restaurants:**
| Name | Latitude | Longitude |
|------|----------|-----------|
| Dominos | 16.46308457 | 80.50843255 |
| US Pizza | 16.46277462 | 80.50822267 |
| Chat & Chill | 16.46295468 | 80.50807783 |
| Paradise | 16.46286593 | 80.50807314 |
| Total Fresh | 16.46311866 | 80.50826089 |
| Baskin Robbins | 16.46302220 | 80.50831923 |
| Nescafe | 16.46288008 | 80.50844664 |

**5 Delivery Blocks:**
| Name | Latitude | Longitude |
|------|----------|-----------|
| SR Block | 16.46263529 | 80.50647169 |
| C Block | 16.46164686 | 80.50569337 |
| Admin Block | 16.46487458 | 80.50791898 |
| Yamuna Hostel | 16.46625427 | 80.50757918 |
| V & G Hostels | 16.46388678 | 80.50665801 |

### Menu Items (35 total — 5 per restaurant)

Each restaurant has 5 menu items with name, description, price (₹), category, and Unsplash image URL. All images are free-to-use Unsplash URLs that don't require an API key.

---

## 7. Migration Script (`db/migrate.py`)

### Usage
```bash
# Full migration (schema + seed)
python db/migrate.py

# Schema only (skip seed data)
python db/migrate.py --schema-only

# Seed only (skip table creation)
python db/migrate.py --seed-only

# DANGER: Drop all tables and recreate
python db/migrate.py --reset
```

### What It Does
1. Connects to PostgreSQL using `DATABASE_URL` env (or default localhost)
2. Runs `schema.sql` — creates extensions, enums, tables, constraints, indexes
3. Runs `seed.sql` — inserts locations, restaurants, menus, home reservations
4. Verifies: prints table list, location counts, home pad statuses, menu items per restaurant

### Docker Auto-Migration
When using `docker-compose up`, PostgreSQL auto-initializes:
```yaml
volumes:
  - ./db/schema.sql:/docker-entrypoint-initdb.d/01_schema.sql
  - ./db/seed.sql:/docker-entrypoint-initdb.d/02_seed.sql
```

---

## 8. How backend-orders Connects

`database.py` detects the database type and creates the appropriate connection:

```python
DATABASE_URL = os.getenv("DATABASE_URL", f"sqlite:///{DB_PATH}")
_is_postgres = DATABASE_URL.startswith("postgresql")

if _is_postgres:
    # Custom asyncpg wrapper with SSL for AWS RDS
    database = _AsyncPGDatabase()    # pool: min=1, max=5
else:
    # SQLite for offline development
    database = databases.Database(DATABASE_URL)
```

**SQLAlchemy table definitions** in `database.py` mirror the PostgreSQL schema exactly, defining all columns for: `orders`, `order_items`, `locations`, `home_location_reservations`, `restaurants`, `menu_items`.

---

## 9. Mobile Local Database (Android Room DB)

To support offline capability, cart preservation, and active order tracking without continuous polling, the native Android application (`Skyro_app`) utilizes a local SQLite database accessed via **Jetpack Room**.

### Entities & Server Correlation

| Room Entity | Corresponds To | Columns / Fields | Purpose |
|-------------|----------------|------------------|---------|
| `CartItem` | *In-memory only on Web* | `id`, `name`, `price`, `quantity`, `restaurantName`, `restaurantId`, `menuItemId` | Stores current cart state persistently across app launches |
| `DeliveryOrder` | `orders` table | `orderId` (local), `restaurantName`, `itemsSummary`, `totalPrice`, `droneId`, `etaMinutes`, `status`, `serverOrderId`, `deliveryLocationName` | Tracks local history and active deliveries. `serverOrderId` maps directly to the `id` column of the `orders` PostgreSQL table. |
| `UserPreference` | *AWS Cognito / localStorage on Web* | `isLoggedIn`, `userName`, `phoneNumber`, `userEmail`, `address`, `awsApiUrl` (custom endpoint URL overrides), `themeMode`, `selectedDeliveryLocationId`, `selectedDeliveryLocationName` | Stores user-specific settings, custom API configurations, and selected themes/locations. |

### Caching and Synchronization Strategy
1. **Local Writes**: Adding an item to the cart or checking out updates the Room DB first.
2. **Server Handshake**: On checkout, the order is posted to the backend orders API. The resulting server UUID is written to `serverOrderId` in the local Room record.
3. **WebSocket Sync**: Real-time status changes (`Placed` → `Cooking` → `En Route` → `Delivered`) pushed via WebSocket are intercepted by the `SkyroViewModel` and written directly to the local Room DB, triggering automatic UI refreshes via Room Flow observations.

---

*Document generated: June 2026 | Project: Skyro Drone Delivery System | Campus: SRM University, Amaravati*
