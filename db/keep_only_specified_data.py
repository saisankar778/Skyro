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
DECLARE
    keep_restaurants TEXT[] := ARRAY['Dominos', 'US Pizza', 'Chat & Chill', 'Baskin Robbins', 'Paradise', 'Total Fresh', 'Nescafe'];
    keep_locations TEXT[] := ARRAY['SR Block', 'C Block', 'Admin Block', 'Yamuna Hostel', 'V & G Hostels'];
    keep_canteen_locs TEXT[] := ARRAY['Dominos', 'US_Pizza', 'Chat_and_Chill', 'Paradise', 'Total_Fresh', 'Baskin_Robins', 'Nescafe'];
    keep_home_locs TEXT[] := ARRAY['HOME_1', 'HOME_2', 'HOME_3', 'HOME_4', 'HOME_5'];
BEGIN
    -- 1. Delete order items and orders for restaurants to delete
    DELETE FROM order_items WHERE order_id IN (
        SELECT id FROM orders WHERE restaurant_id IN (
            SELECT id FROM restaurants WHERE name NOT IN (SELECT unnest(keep_restaurants))
        )
    );
    DELETE FROM orders WHERE restaurant_id IN (
        SELECT id FROM restaurants WHERE name NOT IN (SELECT unnest(keep_restaurants))
    );

    -- 2. Delete menu items for restaurants to delete
    DELETE FROM menu_items WHERE restaurant_id IN (
        SELECT id FROM restaurants WHERE name NOT IN (SELECT unnest(keep_restaurants))
    );

    -- 3. Delete restaurants to delete
    DELETE FROM restaurants WHERE name NOT IN (SELECT unnest(keep_restaurants));

    -- 4. Clean orders to start fresh
    DELETE FROM order_items;
    DELETE FROM orders;
    DELETE FROM delivery_missions;

    -- 5. Free drone references to locations to prevent foreign key errors
    UPDATE drones SET current_location_id = NULL;
    DELETE FROM home_location_reservations;

    -- 6. Delete non-kept locations
    DELETE FROM locations
    WHERE name NOT IN (SELECT unnest(keep_home_locs))
      AND name NOT IN (SELECT unnest(keep_canteen_locs))
      AND name NOT IN (SELECT unnest(keep_locations));

    -- 7. Upsert specified delivery blocks
    INSERT INTO locations (name, type, latitude, longitude, is_active) VALUES
      ('SR Block',        'DELIVERY_BLOCK', 16.462635, 80.506471, true),
      ('C Block',         'DELIVERY_BLOCK', 16.461646, 80.505693, true),
      ('Admin Block',     'DELIVERY_BLOCK', 16.464874, 80.507918, true),
      ('Yamuna Hostel',   'DELIVERY_BLOCK', 16.466254, 80.507579, true),
      ('V & G Hostels',   'DELIVERY_BLOCK', 16.463886, 80.506658, true)
    ON CONFLICT (name) DO UPDATE
      SET latitude = EXCLUDED.latitude,
          longitude = EXCLUDED.longitude,
          is_active = true;

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

    print(f"Connecting to database at {host}:{port}/{db}...")
    conn = await asyncpg.connect(
        host=host, port=port, user=user, password=password,
        database=db, ssl=ctx
    )
    
    print("Executing database pruning and cleanup...")
    await conn.execute(SQL_CLEANUP)
    print("Pruning completed successfully!\n")
    
    # Verify results
    print("--- Verifying Restaurants ---")
    rows = await conn.fetch("SELECT name FROM restaurants")
    for r in rows:
        print(f"- {r['name']}")
        
    print("\n--- Verifying Locations ---")
    rows = await conn.fetch("SELECT name, type FROM locations")
    for r in rows:
        print(f"- {r['name']} ({r['type']})")
        
    await conn.close()

if __name__ == "__main__":
    asyncio.run(run())
