import asyncio
import asyncpg
import ssl
import os
import re

DATABASE_URL = os.environ.get(
    "DATABASE_URL",
    "postgresql+asyncpg://skyro_admin:sky517227@skyro-db.cl4o2c2matz8.ap-south-1.rds.amazonaws.com:5432/skyro?sslmode=require"
)

SQL_SEEDS = """
-- 1. Clean up old records for these specific canteens to prevent duplicates/conflicts
DELETE FROM menu_items WHERE restaurant_id IN (
    SELECT id FROM restaurants WHERE name IN ('Ak Bakers', 'Bhimas Indian Kitchen', 'The Pizza Palace', 'Sri Venkateswara Sweets')
);
DELETE FROM restaurants WHERE name IN ('Ak Bakers', 'Bhimas Indian Kitchen', 'The Pizza Palace', 'Sri Venkateswara Sweets');

-- 2. Insert Locations for Canteens and Delivery Blocks
INSERT INTO locations (name, type, latitude, longitude, is_active) VALUES
  ('Ak_Bakers',                'RESTAURANT', 16.462912, 80.508112, true),
  ('Bhimas_Indian_Kitchen',    'RESTAURANT', 16.463050, 80.508250, true),
  ('The_Pizza_Palace',         'RESTAURANT', 16.462800, 80.508350, true),
  ('Sri_Venkateswara_Sweets',  'RESTAURANT', 16.462950, 80.508500, true),
  ('SRM AP SR Block',                  'DELIVERY_BLOCK', 16.462635, 80.506471, true),
  ('SRM AP Campus',                    'DELIVERY_BLOCK', 16.461646, 80.505693, true),
  ('SRM Girls Hostel Block',           'DELIVERY_BLOCK', 16.464874, 80.507918, true),
  ('SRM Boys Hostel Block (Maha Mani)','DELIVERY_BLOCK', 16.466254, 80.507579, true),
  ('SRM AP V Block',                   'DELIVERY_BLOCK', 16.463886, 80.506658, true),
  ('SRM Research Labs Tower',          'DELIVERY_BLOCK', 16.462800, 80.507000, true)
ON CONFLICT (name) DO UPDATE
  SET latitude  = EXCLUDED.latitude,
      longitude = EXCLUDED.longitude,
      is_active = TRUE;

-- 3. Insert Canteens (Restaurants)
INSERT INTO restaurants (name, tagline, rating, cuisine, delivery_time_min, price_for_two, offer, image_url, location_id)
SELECT r.name, r.tagline, r.rating, r.cuisine, r.delivery_time_min, r.price_for_two, r.offer, r.image_url, l.id
FROM (VALUES
  ('Ak Bakers', 'Freshly Baked Cakes & Shakes', 4.6, 'Bakery, Indian', 45, 300, '🔥 60% off upto ₹120', 'https://images.unsplash.com/photo-1578985545062-69928b1d9587?w=600&q=80', 'Ak_Bakers'),
  ('Bhimas Indian Kitchen', 'Traditional North Indian & Veg Biryani', 4.5, 'North Indian, Biryani', 25, 250, '★ FLAT 50% OFF', 'https://images.unsplash.com/photo-1589301760014-d929f3979dbc?w=600&q=80', 'Bhimas_Indian_Kitchen'),
  ('The Pizza Palace', 'Delicious Loaded Pizzas & Parcels', 4.7, 'Pizzas, Italian, Fast Food', 30, 400, '🎁 FREE Garlic Bread', 'https://images.unsplash.com/photo-1513104890138-7c749659a591?w=600&q=80', 'The_Pizza_Palace'),
  ('Sri Venkateswara Sweets', 'Traditional Sweets & Hot Dosa', 4.4, 'Sweets, South Indian', 15, 150, '🔥 Buy 1 Get 1 Free', 'https://images.unsplash.com/photo-1509042239860-f550ce710b93?w=600&q=80', 'Sri_Venkateswara_Sweets')
) AS r(name, tagline, rating, cuisine, delivery_time_min, price_for_two, offer, image_url, loc_name)
JOIN locations l ON l.name = r.loc_name;

-- 4. Insert Food Categories
INSERT INTO food_categories (name, emoji, sort_order) VALUES
  ('Specials', '🎂', 9),
  ('South Indian', '🥞', 10),
  ('North Indian', '🥘', 11)
ON CONFLICT (name) DO UPDATE
  SET emoji = EXCLUDED.emoji,
      sort_order = EXCLUDED.sort_order;

-- 5. Insert Menu Items (9 items per restaurant)
-- Ak Bakers
INSERT INTO menu_items (restaurant_id, name, description, price, category, image_url, is_veg, weight_grams)
SELECT r.id, m.name, m.description, m.price, m.category, m.image_url, m.is_veg, m.weight_grams
FROM restaurants r,
(VALUES
  ('Strawberry Shake', 'Rich, creamy strawberry milkshake blended with premium dairy and strawberry fruit chunks.', 99.0, 'Beverages', 'https://images.unsplash.com/photo-1579954115545-a95591f28bfc?w=400&q=80', true, 380),
  ('Choco Cheesecake', 'Layers of luxurious chocolate base infused with real creamy cheesecake glaze.', 149.0, 'Desserts', 'https://images.unsplash.com/photo-1606313564200-e75d5e30476c?w=400&q=80', true, 200),
  ('Red Velvet Cake Slice', 'Delightful red velvet sponge layered with silky smooth whipping cream and cheese sprinkles.', 120.0, 'Desserts', 'https://images.unsplash.com/photo-1616260849314-dab4f194148e?w=400&q=80', true, 200),
  ('Pineapple Pastry', 'Light and airy vanilla cake layers filled with chopped pineapples and cream.', 80.0, 'Desserts', 'https://images.unsplash.com/photo-1550617931-e17a7b70dce2?w=400&q=80', true, 150),
  ('Black Forest Cake Slice', 'Layers of rich chocolate sponge cake, whipped cream, and sweet cherries.', 90.0, 'Desserts', 'https://images.unsplash.com/photo-1606313564200-e75d5e30476c?w=400&q=80', true, 180),
  ('Veg Puff', 'Crispy, flaky golden puff pastry stuffed with a spiced mixed vegetable filling.', 40.0, 'Snacks', 'https://images.unsplash.com/photo-1601050690597-df0568f70950?w=400&q=80', true, 100),
  ('Paneer Puff', 'Crispy puff pastry stuffed with spiced cottage cheese cubes.', 50.0, 'Snacks', 'https://images.unsplash.com/photo-1626700051175-6818013e1d4f?w=400&q=80', true, 120),
  ('Chocolate Muffin', 'Moist double chocolate chip muffin baked fresh daily.', 70.0, 'Snacks', 'https://images.unsplash.com/photo-1607958996333-41aef7caefaa?w=400&q=80', true, 150),
  ('Blueberry Muffin', 'Sweet muffin loaded with real blueberries and a light streusel crumble.', 80.0, 'Snacks', 'https://images.unsplash.com/photo-1509042239860-f550ce710b93?w=400&q=80', true, 150)
) AS m(name, description, price, category, image_url, is_veg, weight_grams)
WHERE r.name = 'Ak Bakers';

-- Bhimas Indian Kitchen
INSERT INTO menu_items (restaurant_id, name, description, price, category, image_url, is_veg, weight_grams)
SELECT r.id, m.name, m.description, m.price, m.category, m.image_url, m.is_veg, m.weight_grams
FROM restaurants r,
(VALUES
  ('Kaju Paneer Biryani', 'Fragrant steamed saffron basmati rice layered with generous fried cashew nuts and tender paneer.', 199.0, 'Biryani', 'https://images.unsplash.com/photo-1563379091339-03b21ab4a4f8?w=400&q=80', true, 400),
  ('Veg Dum Biryani Royal', 'Fresh garden vegetables cooked with aromatic organic spices and layered in clay handi pot.', 149.0, 'Biryani', 'https://images.unsplash.com/photo-1596797038530-2c107229654b?w=400&q=80', true, 400),
  ('Dal Makhani Premium', 'Slow 12-hour simmered delicious black lentils loaded with rich processing butter cream.', 120.0, 'Snacks', 'https://images.unsplash.com/photo-1546833999-b9f581a1996d?w=400&q=80', true, 300),
  ('Paneer Butter Masala', 'Juicy paneer cubes cooked in a rich, mild, and creamy tomato and butter base.', 160.0, 'Snacks', 'https://images.unsplash.com/photo-1626700051175-6818013e1d4f?w=400&q=80', true, 350),
  ('Butter Naan (1pc)', 'Tandoor-baked flatbread brushed generously with melted butter.', 40.0, 'Snacks', 'https://images.unsplash.com/photo-1571047736213-3f0c5b1c8d5f?w=400&q=80', true, 100),
  ('Masala Kulcha', 'Leavened flatbread stuffed with spiced potatoes and baked to a golden brown.', 60.0, 'Snacks', 'https://images.unsplash.com/photo-1601050690597-df0568f70950?w=400&q=80', true, 120),
  ('Jeera Rice', 'Aromatic basmati rice tempered with cumin seeds and fresh ghee.', 110.0, 'Biryani', 'https://images.unsplash.com/photo-1596797038530-2c107229654b?w=400&q=80', true, 350),
  ('Mixed Veg Curry', 'Medley of fresh seasonal vegetables cooked in a semi-spicy onion gravy.', 130.0, 'Snacks', 'https://images.unsplash.com/photo-1546833999-b9f581a1996d?w=400&q=80', true, 300),
  ('Garlic Naan', 'Flatbread infused with minced garlic and baked in clay tandoor oven.', 50.0, 'Snacks', 'https://images.unsplash.com/photo-1571047736213-3f0c5b1c8d5f?w=400&q=80', true, 100)
) AS m(name, description, price, category, image_url, is_veg, weight_grams)
WHERE r.name = 'Bhimas Indian Kitchen';

-- The Pizza Palace
INSERT INTO menu_items (restaurant_id, name, description, price, category, image_url, is_veg, weight_grams)
SELECT r.id, m.name, m.description, m.price, m.category, m.image_url, m.is_veg, m.weight_grams
FROM restaurants r,
(VALUES
  ('Paneer & Capsicum Pizza Mania', 'Fresh green capsicum, tender juicy paneer cubes, and real mozzarella cheese on Classic Hand Tossed crust.', 99.0, 'Pizza', 'https://images.unsplash.com/photo-1534308983496-4fabb1a015ee?w=400&q=80', true, 350),
  ('Tandoori Loaded Paneer Parcel', 'Golden flaky pocket packed with spicy tandoori paneer stuffing and premium cheese sauce.', 75.0, 'Snacks', 'https://images.unsplash.com/photo-1626700051175-6818013e1d4f?w=400&q=80', true, 150),
  ('Tandoori Loaded Chicken Parcel', 'Succulent spice-marinated bite-sized chicken tandoori stuffed inside flaky pocket pane.', 75.0, 'Snacks', 'https://images.unsplash.com/photo-1601050690597-df0568f70950?w=400&q=80', false, 150),
  ('Classic Fresh Pan', 'Fresh hand-pan tossed basic mozzarella single-crust classic cheese pizza block.', 79.0, 'Pizza', 'https://images.unsplash.com/photo-1574071318508-1cdbab80d002?w=400&q=80', true, 300),
  ('Tandoori Loaded Veg Taco (Single)', 'Tandoori-spiced pocket taco stuffed with fresh colorful dynamic garden toppings.', 95.0, 'Snacks', 'https://images.unsplash.com/photo-1601050690117-898bc9ce48ee?w=400&q=80', true, 200),
  ('Onion Pizza Mania', 'Crispy pan pizza topped with sweet onions and liquid mozzarella.', 89.0, 'Pizza', 'https://images.unsplash.com/photo-1513104890138-7c749659a591?w=400&q=80', true, 300),
  ('Golden Corn Pizza Mania', 'Sweet kernels of golden sweet corn baked with mozzarella.', 99.0, 'Pizza', 'https://images.unsplash.com/photo-1565299624946-b28f40a0ae38?w=400&q=80', true, 320),
  ('Margherita Pizza', 'Double cheese margherita baked with extra marinara sauce.', 199.0, 'Pizza', 'https://images.unsplash.com/photo-1574071318508-1cdbab80d002?w=400&q=80', true, 350),
  ('Veg Supreme Pizza', 'Capsicum, onion, tomato, paneer, olives and sweetcorn.', 299.0, 'Pizza', 'https://images.unsplash.com/photo-1534308983496-4fabb1a015ee?w=400&q=80', true, 450)
) AS m(name, description, price, category, image_url, is_veg, weight_grams)
WHERE r.name = 'The Pizza Palace';

-- Sri Venkateswara Sweets
INSERT INTO menu_items (restaurant_id, name, description, price, category, image_url, is_veg, weight_grams)
SELECT r.id, m.name, m.description, m.price, m.category, m.image_url, m.is_veg, m.weight_grams
FROM restaurants r,
(VALUES
  ('Plain Dosa', 'Crispy, paper-thin golden crepe made from fermented rice-lentil flour served with fresh coconut chutney.', 49.0, 'Snacks', 'https://images.unsplash.com/photo-1589301760014-d929f3979dbc?w=400&q=80', true, 150),
  ('Rava Dosa', 'Delectable crispy semolina crepe mixed with fresh crushed green chilies, onions, and deep flavors.', 99.0, 'Snacks', 'https://images.unsplash.com/photo-1596797038530-2c107229654b?w=400&q=80', true, 200),
  ('Motichoor Laddu (4pc)', 'Mouth-watering orange sweet round laddus cooked perfectly with organic pure milk ghee.', 80.0, 'Desserts', 'https://images.unsplash.com/photo-1601050690117-898bc9ce48ee?w=400&q=80', true, 150),
  ('Kesar Rasgulla (2pc)', 'Spongy, extremely juicy cottage cheese dumplings floating in delicate saffron-perfumed simple sugar syrup.', 60.0, 'Desserts', 'https://images.unsplash.com/photo-1555949258-eb67b1ef0ceb?w=400&q=80', true, 150),
  ('Idli (3pc)', 'Soft and fluffy steamed rice-lentil cakes served with sambar and peanut chutney.', 40.0, 'Snacks', 'https://images.unsplash.com/photo-1589301760014-d929f3979dbc?w=400&q=80', true, 180),
  ('Vada (2pc)', 'Crispy, deep-fried savory lentil doughnuts spiced with black pepper and ginger.', 50.0, 'Snacks', 'https://images.unsplash.com/photo-1601050690597-df0568f70950?w=400&q=80', true, 120),
  ('Onion Dosa', 'Golden crepe topped with finely chopped onions, green chillies and coriander.', 79.0, 'Snacks', 'https://images.unsplash.com/photo-1596797038530-2c107229654b?w=400&q=80', true, 220),
  ('Kaju Katli (250g)', 'Rich and premium diamond-shaped cashew fudge sweets.', 250.0, 'Desserts', 'https://images.unsplash.com/photo-1555949258-eb67b1ef0ceb?w=400&q=80', true, 250),
  ('Gulab Jamun (2pc)', 'Delicate fried dough balls soaked in a sweet cardamom syrup.', 50.0, 'Desserts', 'https://images.unsplash.com/photo-1601050690117-898bc9ce48ee?w=400&q=80', true, 120)
) AS m(name, description, price, category, image_url, is_veg, weight_grams)
WHERE r.name = 'Sri Venkateswara Sweets';
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
    print("Connected. Seeding missing UI canteens and menu items...")
    await conn.execute(SQL_SEEDS)
    print("Seeding completed successfully!\n")

    # Verifications
    rest_count = await conn.fetchval("SELECT COUNT(*) FROM restaurants WHERE name IN ('Ak Bakers', 'Bhimas Indian Kitchen', 'The Pizza Palace', 'Sri Venkateswara Sweets')")
    menu_count = await conn.fetchval("SELECT COUNT(*) FROM menu_items WHERE restaurant_id IN (SELECT id FROM restaurants WHERE name IN ('Ak Bakers', 'Bhimas Indian Kitchen', 'The Pizza Palace', 'Sri Venkateswara Sweets'))")
    loc_count = await conn.fetchval("SELECT COUNT(*) FROM locations WHERE type = 'DELIVERY_BLOCK'")
    cat_count = await conn.fetchval("SELECT COUNT(*) FROM food_categories")

    print(f"Seeded restaurants added: {rest_count}")
    print(f"Seeded menu items added  : {menu_count}")
    print(f"Total delivery blocks    : {loc_count}")
    print(f"Total food categories    : {cat_count}")

    await conn.close()

if __name__ == "__main__":
    asyncio.run(run())
