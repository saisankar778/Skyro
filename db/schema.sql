-- =============================================================================
-- SKYRO DRONE DELIVERY — FULL PRODUCTION SCHEMA
-- Database: PostgreSQL (Amazon RDS)
-- Run once: psql $DATABASE_URL -f schema.sql
-- =============================================================================

-- ---------------------------------------------------------------------------
-- 0. EXTENSIONS
-- ---------------------------------------------------------------------------
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- ---------------------------------------------------------------------------
-- 1. ENUM TYPES
-- ---------------------------------------------------------------------------
DO $$ BEGIN

  CREATE TYPE location_type AS ENUM (
    'RESTAURANT',
    'DELIVERY_BLOCK',
    'HOME'
  );

EXCEPTION WHEN duplicate_object THEN NULL; END $$;

DO $$ BEGIN

  CREATE TYPE order_status AS ENUM (
    'CREATED',
    'CONFIRMED',
    'PREPARING',
    'READY_FOR_PICKUP',
    'DRONE_ASSIGNED',
    'IN_FLIGHT',
    'DELIVERED',
    'FAILED',
    'CANCELLED'
  );

EXCEPTION WHEN duplicate_object THEN NULL; END $$;

DO $$ BEGIN

  CREATE TYPE drone_status AS ENUM (
    'IDLE',
    'RESERVED',
    'ASSIGNED',
    'IN_FLIGHT',
    'RETURNING_HOME',
    'CHARGING',
    'MAINTENANCE'
  );

EXCEPTION WHEN duplicate_object THEN NULL; END $$;

DO $$ BEGIN

  CREATE TYPE mission_status AS ENUM (
    'CREATED',
    'ASSIGNED',
    'IN_PROGRESS',
    'DELIVERED',
    'RETURNING_HOME',
    'COMPLETED',
    'FAILED'
  );

EXCEPTION WHEN duplicate_object THEN NULL; END $$;

-- ---------------------------------------------------------------------------
-- 2. LOCATIONS (CORE TABLE — shared by all microservices)
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS locations (
    id          UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name        VARCHAR(100) UNIQUE NOT NULL,
    type        location_type NOT NULL,
    latitude    DOUBLE PRECISION NOT NULL,
    longitude   DOUBLE PRECISION NOT NULL,
    is_active   BOOLEAN DEFAULT TRUE,
    created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ---------------------------------------------------------------------------
-- 3. USERS
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS users (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name            VARCHAR(100) NOT NULL,
    email           VARCHAR(150) UNIQUE NOT NULL,
    phone           VARCHAR(15),
    password_hash   TEXT NOT NULL,
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ---------------------------------------------------------------------------
-- 4. RESTAURANTS
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS restaurants (
    id                UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name              VARCHAR(100) NOT NULL,
    tagline           TEXT,
    rating            DECIMAL(2,1) DEFAULT 0,
    location_id       UUID NOT NULL REFERENCES locations(id),
    is_active         BOOLEAN DEFAULT TRUE,
    -- Rich display fields (all editable in DB without code change)
    cuisine           VARCHAR(100),
    delivery_time_min INT  DEFAULT 20,   -- estimated delivery time in minutes
    price_for_two     INT  DEFAULT 300,  -- indicative price for two people (₹)
    offer             TEXT,              -- e.g. "50% OFF", "Buy 1 Get 1"
    image_url         TEXT,              -- hero image shown in frontend card
    created_at        TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ---------------------------------------------------------------------------
-- 5. MENU ITEMS
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS menu_items (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    restaurant_id   UUID REFERENCES restaurants(id) ON DELETE CASCADE,
    name            VARCHAR(100) NOT NULL,
    description     TEXT,
    price           DECIMAL(10,2) NOT NULL,
    category        VARCHAR(50),   -- e.g. "Pizza", "Desserts", "Beverages"
    image_url       TEXT,          -- item photo shown in menu card
    is_available    BOOLEAN DEFAULT TRUE
);

-- ---------------------------------------------------------------------------
-- 6. ORDERS
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS orders (
    id                  UUID PRIMARY KEY DEFAULT uuid_generate_v4(),

    -- Legacy string ID support (frontend uses ORD-<timestamp>)
    legacy_id           VARCHAR(64) UNIQUE,

    user_id             UUID REFERENCES users(id),
    restaurant_id       UUID REFERENCES restaurants(id),

    pickup_location_id  UUID REFERENCES locations(id),
    drop_location_id    UUID REFERENCES locations(id),

    status              order_status NOT NULL DEFAULT 'CREATED',

    -- Fleet AI atomic assignment lock (UUID of assigned drone)
    assigned_drone_id   VARCHAR(64),

    total_amount        DECIMAL(10,2),

    created_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at          TIMESTAMP,
    completed_at        TIMESTAMP
);

-- ---------------------------------------------------------------------------
-- 7. ORDER ITEMS
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS order_items (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    order_id        UUID REFERENCES orders(id) ON DELETE CASCADE,
    menu_item_id    UUID REFERENCES menu_items(id),

    -- Denormalized name/price for historical accuracy
    item_name       VARCHAR(100),
    quantity        INT NOT NULL CHECK (quantity > 0),
    price_at_time   DECIMAL(10,2) NOT NULL
);

-- ---------------------------------------------------------------------------
-- 8. DRONES
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS drones (
    id                  UUID PRIMARY KEY DEFAULT uuid_generate_v4(),

    -- MAVLink / dronekit connection identifier
    drone_key           VARCHAR(64) UNIQUE NOT NULL,

    name                VARCHAR(50),
    status              drone_status DEFAULT 'IDLE',
    battery_level       INT CHECK (battery_level >= 0 AND battery_level <= 100),

    current_location_id UUID REFERENCES locations(id),

    last_heartbeat      TIMESTAMP,
    last_updated        TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ---------------------------------------------------------------------------
-- 9. DELIVERY MISSIONS
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS delivery_missions (
    id                  UUID PRIMARY KEY DEFAULT uuid_generate_v4(),

    order_id            UUID UNIQUE REFERENCES orders(id),
    drone_id            UUID REFERENCES drones(id),

    pickup_location_id  UUID REFERENCES locations(id),
    drop_location_id    UUID REFERENCES locations(id),
    home_location_id    UUID REFERENCES locations(id),

    status              mission_status DEFAULT 'CREATED',

    ai_score            DECIMAL(5,4),      -- scheduler confidence score
    eta_seconds         INT,               -- estimated flight time

    started_at          TIMESTAMP,
    completed_at        TIMESTAMP,
    created_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ---------------------------------------------------------------------------
-- 10. HOME LOCATION RESERVATIONS (CRITICAL — drone return-to-home slots)
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS home_location_reservations (
    location_id         UUID PRIMARY KEY REFERENCES locations(id),
    is_reserved         BOOLEAN DEFAULT FALSE,
    reserved_by_drone   VARCHAR(64),           -- drone_key (MAVLink ID)
    reserved_at         TIMESTAMP,
    released_at         TIMESTAMP
);

-- ---------------------------------------------------------------------------
-- 11. SYSTEM EVENTS (audit log + debugging)
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS system_events (
    id          UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    entity_type VARCHAR(50),
    entity_id   UUID,
    event_type  VARCHAR(50),
    payload     JSONB,
    created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ---------------------------------------------------------------------------
-- CONSTRAINTS
-- ---------------------------------------------------------------------------

-- Prevent duplicate missions per order (already enforced by UNIQUE above)
ALTER TABLE delivery_missions
    DROP CONSTRAINT IF EXISTS unique_order_mission;
ALTER TABLE delivery_missions
    ADD CONSTRAINT unique_order_mission UNIQUE (order_id);

-- Ensure only HOME-type locations can be reserved as home slots
-- (enforced at application layer; DB-level via function check)
CREATE OR REPLACE FUNCTION check_home_location_type()
RETURNS TRIGGER AS $$
BEGIN
    IF (SELECT type FROM locations WHERE id = NEW.location_id) != 'HOME' THEN
        RAISE EXCEPTION 'Only HOME-type locations can be used in home_location_reservations';
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_check_home_type ON home_location_reservations;
CREATE TRIGGER trg_check_home_type
    BEFORE INSERT OR UPDATE ON home_location_reservations
    FOR EACH ROW EXECUTE FUNCTION check_home_location_type();

-- ---------------------------------------------------------------------------
-- INDEXES (query performance)
-- ---------------------------------------------------------------------------
CREATE INDEX IF NOT EXISTS idx_orders_status       ON orders(status);
CREATE INDEX IF NOT EXISTS idx_orders_created_at   ON orders(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_drones_status        ON drones(status);
CREATE INDEX IF NOT EXISTS idx_locations_type       ON locations(type);
CREATE INDEX IF NOT EXISTS idx_missions_status      ON delivery_missions(status);
CREATE INDEX IF NOT EXISTS idx_home_reserved        ON home_location_reservations(is_reserved);
CREATE INDEX IF NOT EXISTS idx_system_events_entity ON system_events(entity_type, entity_id);
