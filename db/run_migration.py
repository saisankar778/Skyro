"""
Run the Skyro migration SQL (veg/weight/categories) against RDS.
Usage: python run_migration.py
"""
import asyncio
import asyncpg
import ssl
import os
import re

DATABASE_URL = os.environ.get(
    "DATABASE_URL",
    "postgresql+asyncpg://skyro_admin:sky517227@skyro-db.cl4o2c2matz8.ap-south-1.rds.amazonaws.com:5432/skyro?sslmode=require"
)

SQL = """
ALTER TABLE menu_items ADD COLUMN IF NOT EXISTS is_veg       BOOLEAN  DEFAULT FALSE;
ALTER TABLE menu_items ADD COLUMN IF NOT EXISTS weight_grams INTEGER  DEFAULT 300;

CREATE TABLE IF NOT EXISTS food_categories (
    id          UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name        VARCHAR(50) UNIQUE NOT NULL,
    emoji       VARCHAR(10) DEFAULT '?',
    sort_order  INT DEFAULT 0
);

INSERT INTO food_categories (name, emoji, sort_order) VALUES
    ('All',        'ALL', 0),
    ('Pizza',      'PIZZA', 1),
    ('Biryani',    'BIRYANI', 2),
    ('Snacks',     'SNACKS', 3),
    ('Beverages',  'DRINKS', 4),
    ('Desserts',   'SWEET', 5),
    ('Healthy',    'HEALTH', 6),
    ('Coffee',     'COFFEE', 7),
    ('Ice Cream',  'ICE', 8)
ON CONFLICT (name) DO UPDATE
    SET emoji = EXCLUDED.emoji,
        sort_order = EXCLUDED.sort_order;

-- Veg flag updates
UPDATE menu_items SET is_veg = TRUE  WHERE name IN ('Farmhouse Pizza', 'Peppy Paneer', 'Margherita', 'Garlic Bread', 'Choco Lava Cake');
UPDATE menu_items SET is_veg = FALSE WHERE name IN ('BBQ Chicken Pizza', 'Chicken Biryani', 'Mutton Biryani');
UPDATE menu_items SET is_veg = TRUE  WHERE name IN ('Double Cheese Pizza', 'Stuffed Crust Pizza', 'Pasta Arrabiata', 'Garlic Dip',
    'Paneer Tikka Roll', 'Aloo Tikki', 'Samosa (2 pcs)', 'Masala Chai', 'Cold Coffee',
    'Veg Biryani', 'Raita', 'Gulab Jamun',
    'Fresh Lime Soda', 'Watermelon Juice', 'Fruit Salad', 'Veg Sandwich', 'Protein Smoothie',
    'Single Scoop', 'Double Scoop', 'Mississippi Mud Pie', 'Cotton Candy Blast', 'Sundae',
    'Cappuccino', 'Latte', 'Chocolate Muffin');

-- Weight updates (grams)
UPDATE menu_items SET weight_grams = 520 WHERE name IN ('Farmhouse Pizza', 'Peppy Paneer', 'Margherita');
UPDATE menu_items SET weight_grams = 540 WHERE name IN ('Double Cheese Pizza', 'BBQ Chicken Pizza', 'Stuffed Crust Pizza');
UPDATE menu_items SET weight_grams = 400 WHERE name IN ('Chicken Biryani', 'Mutton Biryani', 'Veg Biryani');
UPDATE menu_items SET weight_grams = 180 WHERE name IN ('Paneer Tikka Roll');
UPDATE menu_items SET weight_grams = 120 WHERE name IN ('Aloo Tikki', 'Samosa (2 pcs)');
UPDATE menu_items SET weight_grams = 150 WHERE name IN ('Garlic Bread');
UPDATE menu_items SET weight_grams = 200 WHERE name IN ('Pasta Arrabiata');
UPDATE menu_items SET weight_grams = 380 WHERE name IN ('Masala Chai', 'Cold Coffee', 'Fresh Lime Soda', 'Watermelon Juice', 'Protein Smoothie');
UPDATE menu_items SET weight_grams = 350 WHERE name IN ('Cappuccino', 'Latte');
UPDATE menu_items SET weight_grams = 200 WHERE name IN ('Choco Lava Cake', 'Mississippi Mud Pie', 'Gulab Jamun');
UPDATE menu_items SET weight_grams = 150 WHERE name IN ('Single Scoop', 'Sundae');
UPDATE menu_items SET weight_grams = 250 WHERE name IN ('Double Scoop', 'Cotton Candy Blast');
UPDATE menu_items SET weight_grams = 80  WHERE name IN ('Garlic Dip');
UPDATE menu_items SET weight_grams = 90  WHERE name IN ('Raita');
UPDATE menu_items SET weight_grams = 100 WHERE name IN ('Chocolate Muffin');
UPDATE menu_items SET weight_grams = 140 WHERE name IN ('Veg Sandwich', 'Fruit Salad');
"""


async def run():
    url = DATABASE_URL.replace("postgresql+asyncpg://", "").replace("postgresql://", "")
    # strip ssl query string
    url = re.sub(r"\?.*", "", url)
    m = re.match(r"([^:]+):([^@]+)@([^:/]+):?(\d+)?/([^?]+)", url)
    user, password, host, port, db = m.groups()
    port = int(port or 5432)

    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE

    print(f"Connecting to {host}:{port}/{db} ...")
    conn = await asyncpg.connect(
        host=host, port=port, user=user, password=password,
        database=db, ssl=ctx
    )
    print("Connected. Running migration ...")
    await conn.execute(SQL)
    print("Migration SQL executed successfully!\n")

    # Verify
    veg_count = await conn.fetchval("SELECT COUNT(*) FROM menu_items WHERE is_veg = TRUE")
    nonveg_count = await conn.fetchval("SELECT COUNT(*) FROM menu_items WHERE is_veg = FALSE")
    cat_count = await conn.fetchval("SELECT COUNT(*) FROM food_categories")
    print(f"Veg items        : {veg_count}")
    print(f"Non-veg items    : {nonveg_count}")
    print(f"Food categories  : {cat_count}")

    cats = await conn.fetch("SELECT name, sort_order FROM food_categories ORDER BY sort_order")
    print("\nCategories seeded:")
    for c in cats:
        print(f"  {c['sort_order']}. {c['name']}")

    sample = await conn.fetch("SELECT name, is_veg, weight_grams FROM menu_items ORDER BY name LIMIT 8")
    print("\nSample menu items (name | veg | weight):")
    for r in sample:
        print(f"  {r['name']:<30} veg={r['is_veg']}  weight={r['weight_grams']}g")

    await conn.close()
    print("\nDone!")


if __name__ == "__main__":
    asyncio.run(run())
