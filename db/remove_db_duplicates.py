import asyncio
import asyncpg
import ssl
import os
import re

DATABASE_URL = os.environ.get(
    "DATABASE_URL",
    "postgresql+asyncpg://skyro_admin:sky517227@skyro-db.cl4o2c2matz8.ap-south-1.rds.amazonaws.com:5432/skyro?sslmode=require"
)

SQL_CLEANUP = """
DO $$
BEGIN
    ---------------------------------------------------------------------------
    -- 1. CLEANUP DUPLICATE LOCATIONS
    ---------------------------------------------------------------------------
    CREATE TEMP TABLE primary_locations AS
    SELECT name, MIN(id::text)::uuid as primary_id
    FROM locations
    GROUP BY name;

    -- Update restaurants location_id references
    UPDATE restaurants r
    SET location_id = pl.primary_id
    FROM locations l
    JOIN primary_locations pl ON pl.name = l.name
    WHERE r.location_id = l.id AND l.id != pl.primary_id;

    -- Update orders location references
    UPDATE orders o
    SET pickup_location_id = pl.primary_id
    FROM locations l
    JOIN primary_locations pl ON pl.name = l.name
    WHERE o.pickup_location_id = l.id AND l.id != pl.primary_id;

    UPDATE orders o
    SET drop_location_id = pl.primary_id
    FROM locations l
    JOIN primary_locations pl ON pl.name = l.name
    WHERE o.drop_location_id = l.id AND l.id != pl.primary_id;

    -- Update delivery_missions location references
    UPDATE delivery_missions dm
    SET pickup_location_id = pl.primary_id
    FROM locations l
    JOIN primary_locations pl ON pl.name = l.name
    WHERE dm.pickup_location_id = l.id AND l.id != pl.primary_id;

    UPDATE delivery_missions dm
    SET drop_location_id = pl.primary_id
    FROM locations l
    JOIN primary_locations pl ON pl.name = l.name
    WHERE dm.drop_location_id = l.id AND l.id != pl.primary_id;

    UPDATE delivery_missions dm
    SET home_location_id = pl.primary_id
    FROM locations l
    JOIN primary_locations pl ON pl.name = l.name
    WHERE dm.home_location_id = l.id AND l.id != pl.primary_id;

    -- Update drones current_location_id references
    UPDATE drones d
    SET current_location_id = pl.primary_id
    FROM locations l
    JOIN primary_locations pl ON pl.name = l.name
    WHERE d.current_location_id = l.id AND l.id != pl.primary_id;

    -- Delete conflicting home_location_reservations before pruning locations
    DELETE FROM home_location_reservations hlr
    WHERE hlr.location_id IN (
        SELECT l.id FROM locations l
        JOIN primary_locations pl ON pl.name = l.name
        WHERE l.id != pl.primary_id
    );

    -- Delete duplicate locations
    DELETE FROM locations l
    WHERE l.id NOT IN (SELECT primary_id FROM primary_locations);

    DROP TABLE primary_locations;

    ---------------------------------------------------------------------------
    -- 2. CLEANUP DUPLICATE RESTAURANTS
    ---------------------------------------------------------------------------
    CREATE TEMP TABLE primary_restaurants AS
    SELECT name, MIN(id::text)::uuid as primary_id
    FROM restaurants
    GROUP BY name;

    -- Update orders restaurant references
    UPDATE orders o
    SET restaurant_id = pr.primary_id
    FROM restaurants r
    JOIN primary_restaurants pr ON pr.name = r.name
    WHERE o.restaurant_id = r.id AND r.id != pr.primary_id;

    -- Update menu_items restaurant references
    UPDATE menu_items mi
    SET restaurant_id = pr.primary_id
    FROM restaurants r
    JOIN primary_restaurants pr ON pr.name = r.name
    WHERE mi.restaurant_id = r.id AND r.id != pr.primary_id;

    -- Delete duplicate restaurants
    DELETE FROM restaurants r
    WHERE r.id NOT IN (SELECT primary_id FROM primary_restaurants);

    DROP TABLE primary_restaurants;

    ---------------------------------------------------------------------------
    -- 3. CLEANUP DUPLICATE MENU ITEMS
    ---------------------------------------------------------------------------
    CREATE TEMP TABLE primary_menu_items AS
    SELECT restaurant_id, name, MIN(id::text)::uuid as primary_id
    FROM menu_items
    GROUP BY restaurant_id, name;

    -- Update order_items menu_item_id references
    UPDATE order_items oi
    SET menu_item_id = pmi.primary_id
    FROM menu_items mi
    JOIN primary_menu_items pmi ON pmi.restaurant_id = mi.restaurant_id AND pmi.name = mi.name
    WHERE oi.menu_item_id = mi.id AND mi.id != pmi.primary_id;

    -- Delete duplicate menu items
    DELETE FROM menu_items mi
    WHERE mi.id NOT IN (SELECT primary_id FROM primary_menu_items);

    DROP TABLE primary_menu_items;

    ---------------------------------------------------------------------------
    -- 4. CLEANUP DUPLICATE FOOD CATEGORIES
    ---------------------------------------------------------------------------
    CREATE TEMP TABLE primary_categories AS
    SELECT name, MIN(id::text)::uuid as primary_id
    FROM food_categories
    GROUP BY name;

    -- Delete duplicate food categories
    DELETE FROM food_categories fc
    WHERE fc.id NOT IN (SELECT primary_id FROM primary_categories);

    DROP TABLE primary_categories;

END $$;
"""

async def run():
    url = DATABASE_URL.replace("postgresql+asyncpg://", "").replace("postgresql://", "")
    url = re.sub(r"\?.*", "", url)
    m = re.match(r"([^:]+):([^@]+)@([^:/]+):?(\d+)?/([^?]+)", url)
    user, password, host, port, db = m.groups()
    port = int(port or 5432)

    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE

    print(f"Connecting to AWS RDS at {host}:{port}/{db}...")
    conn = await asyncpg.connect(
        host=host, port=port, user=user, password=password,
        database=db, ssl=ctx
    )
    
    print("Connected. Pruning duplicate records...")
    await conn.execute(SQL_CLEANUP)
    print("Pruning completed successfully!\n")

    # Verifications
    loc_count = await conn.fetchval("SELECT COUNT(*) FROM locations")
    rest_count = await conn.fetchval("SELECT COUNT(*) FROM restaurants")
    menu_count = await conn.fetchval("SELECT COUNT(*) FROM menu_items")
    cat_count = await conn.fetchval("SELECT COUNT(*) FROM food_categories")

    print(f"Total active locations  : {loc_count}")
    print(f"Total active canteens   : {rest_count}")
    print(f"Total active menu items : {menu_count}")
    print(f"Total active categories : {cat_count}")

    await conn.close()

if __name__ == "__main__":
    asyncio.run(run())
