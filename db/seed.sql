-- =============================================================================
-- SKYRO — SEED DATA  (production-grade, DB-driven)
-- Real GPS coordinates for KL University campus, Vijayawada
-- Images: Unsplash free-to-use URLs (no API key needed)
-- Run after schema.sql   —   psql $DATABASE_URL -f seed.sql
-- =============================================================================

-- ---------------------------------------------------------------------------
-- HOME LOCATIONS (5 drone return-to-base pads)
-- ---------------------------------------------------------------------------
INSERT INTO locations (name, type, latitude, longitude) VALUES
  ('HOME_1', 'HOME', 16.46279507215054,  80.50735459755417),
  ('HOME_2', 'HOME', 16.462866449965045, 80.50755119683426),
  ('HOME_3', 'HOME', 16.462835582985836, 80.50771749378666),
  ('HOME_4', 'HOME', 16.462856160972517, 80.50792670608162),
  ('HOME_5', 'HOME', 16.462677389639875, 80.50761959315294)
ON CONFLICT (name) DO UPDATE
  SET latitude  = EXCLUDED.latitude,
      longitude = EXCLUDED.longitude,
      is_active = TRUE;

-- ---------------------------------------------------------------------------
-- RESTAURANT LOCATIONS
-- ---------------------------------------------------------------------------
INSERT INTO locations (name, type, latitude, longitude) VALUES
  ('Dominos',        'RESTAURANT', 16.463084574257913, 80.5084325541339),
  ('US_Pizza',       'RESTAURANT', 16.46277461846416,  80.50822267128899),
  ('Chat_and_Chill', 'RESTAURANT', 16.462954675830282, 80.50807783200786),
  ('Paradise',       'RESTAURANT', 16.46286593329217,  80.50807313814228),
  ('Total_Fresh',    'RESTAURANT', 16.463118656500374, 80.50826089276595),
  ('Baskin_Robins',  'RESTAURANT', 16.463022197299473, 80.50831923080973),
  ('Nescafe',        'RESTAURANT', 16.46288008065604,  80.50844663573295)
ON CONFLICT (name) DO UPDATE
  SET latitude  = EXCLUDED.latitude,
      longitude = EXCLUDED.longitude,
      is_active = TRUE;

-- ---------------------------------------------------------------------------
-- DELIVERY BLOCK LOCATIONS
-- ---------------------------------------------------------------------------
INSERT INTO locations (name, type, latitude, longitude) VALUES
  ('SR_Block',       'DELIVERY_BLOCK', 16.462635294684286, 80.50647168669644),
  ('C_Block',        'DELIVERY_BLOCK', 16.461646855350896, 80.50569336570064),
  ('Admin_Block',    'DELIVERY_BLOCK', 16.464874583335895, 80.50791898212552),
  ('Yamuna_Hostel',  'DELIVERY_BLOCK', 16.466254271237375, 80.50757917761362),
  ('V_and_G_Hostels','DELIVERY_BLOCK', 16.463886777402795, 80.50665800799868)
ON CONFLICT (name) DO UPDATE
  SET latitude  = EXCLUDED.latitude,
      longitude = EXCLUDED.longitude,
      is_active = TRUE;

-- ---------------------------------------------------------------------------
-- RESTAURANTS (with rich display data)
-- ---------------------------------------------------------------------------
INSERT INTO restaurants (name, tagline, rating, cuisine, delivery_time_min, price_for_two, offer, image_url, location_id)
SELECT
  r.name, r.tagline, r.rating, r.cuisine, r.delivery_time_min, r.price_for_two, r.offer, r.image_url, l.id
FROM (VALUES
  ('Dominos',
   'Hot & Fresh Pizzas',
   4.3,
   'Pizza, Fast Food',
   20,
   400,
   '50% OFF on first order',
   'https://images.unsplash.com/photo-1513104890138-7c749659a591?w=600&q=80',
   'Dominos'
  ),
  ('US Pizza',
   'American Style Gourmet Pizza',
   4.2,
   'Pizza, Italian',
   25,
   500,
   'Buy 1 Get 1 Free',
   'https://images.unsplash.com/photo-1565299624946-b28f40a0ae38?w=600&q=80',
   'US_Pizza'
  ),
  ('Chat & Chill',
   'Street Food & Cool Beverages',
   4.5,
   'Street Food, Snacks',
   10,
   200,
   'Free Cold Drink on orders above ₹150',
   'https://images.unsplash.com/photo-1601050690597-df0568f70950?w=600&q=80',
   'Chat_and_Chill'
  ),
  ('Paradise',
   'Legendary Biryani & More',
   4.7,
   'Biryani, Indian',
   20,
   350,
   'Free Raita on every order',
   'https://images.unsplash.com/photo-1563379091339-03b21ab4a4f8?w=600&q=80',
   'Paradise'
  ),
  ('Total Fresh',
   'Healthy Juices & Fresh Meals',
   4.1,
   'Healthy, Juices',
   15,
   180,
   '15% OFF on all combos',
   'https://images.unsplash.com/photo-1610970881699-44a5587cabec?w=600&q=80',
   'Total_Fresh'
  ),
  ('Baskin Robbins',
   'Premium Ice Cream Parlour',
   4.4,
   'Ice Cream, Desserts',
   12,
   250,
   '2 Scoops for the price of 1',
   'https://images.unsplash.com/photo-1497034825429-c343d7c6a68f?w=600&q=80',
   'Baskin_Robins'
  ),
  ('Nescafe',
   'Your Perfect Cup, Every Time',
   4.0,
   'Coffee, Snacks',
   8,
   150,
   'Free Cookie with every coffee',
   'https://images.unsplash.com/photo-1509042239860-f550ce710b93?w=600&q=80',
   'Nescafe'
  )
) AS r(name, tagline, rating, cuisine, delivery_time_min, price_for_two, offer, image_url, loc_name)
JOIN locations l ON l.name = r.loc_name
ON CONFLICT DO NOTHING;

-- ---------------------------------------------------------------------------
-- MENU ITEMS (full catalogue with images & categories)
-- ---------------------------------------------------------------------------

-- ── Dominos ─────────────────────────────────────────────────────────────────
INSERT INTO menu_items (restaurant_id, name, description, price, category, image_url)
SELECT r.id, m.name, m.description, m.price, m.category, m.image_url
FROM restaurants r,
(VALUES
  ('Farmhouse Pizza',     'Loaded with fresh veggies and cheese',        350, 'Pizza',    'https://images.unsplash.com/photo-1534308983496-4fabb1a015ee?w=400&q=80'),
  ('Peppy Paneer',        'Spicy paneer with capsicum on a crispy base', 390, 'Pizza',    'https://images.unsplash.com/photo-1565299585323-38d6b0865b47?w=400&q=80'),
  ('Margherita',          'Classic tomato, basil and mozzarella',        280, 'Pizza',    'https://images.unsplash.com/photo-1574071318508-1cdbab80d002?w=400&q=80'),
  ('Garlic Bread',        'Crispy garlic bread with herb butter',        120, 'Sides',    'https://images.unsplash.com/photo-1619740455993-9d623e1c3527?w=400&q=80'),
  ('Choco Lava Cake',     'Warm chocolate cake with molten centre',      99,  'Desserts', 'https://images.unsplash.com/photo-1606313564200-e75d5e30476c?w=400&q=80')
) AS m(name, description, price, category, image_url)
WHERE r.name = 'Dominos'
ON CONFLICT DO NOTHING;

-- ── US Pizza ─────────────────────────────────────────────────────────────────
INSERT INTO menu_items (restaurant_id, name, description, price, category, image_url)
SELECT r.id, m.name, m.description, m.price, m.category, m.image_url
FROM restaurants r,
(VALUES
  ('Double Cheese Pizza', 'Extra cheese on our signature crust',         400, 'Pizza',      'https://images.unsplash.com/photo-1548369937-47519962c11a?w=400&q=80'),
  ('BBQ Chicken Pizza',   'Smoky BBQ sauce with grilled chicken',        450, 'Pizza',      'https://images.unsplash.com/photo-1590947132387-155cc02f3212?w=400&q=80'),
  ('Stuffed Crust Pizza', 'Cheese-stuffed golden crust',                 420, 'Pizza',      'https://images.unsplash.com/photo-1528137871618-79d2761e3fd5?w=400&q=80'),
  ('Pasta Arrabiata',     'Spicy tomato pasta with penne',               220, 'Pasta',      'https://images.unsplash.com/photo-1555949258-eb67b1ef0ceb?w=400&q=80'),
  ('Garlic Dip',          'Classic creamy garlic dipping sauce',         40,  'Sides',      'https://images.unsplash.com/photo-1571047736213-3f0c5b1c8d5f?w=400&q=80')
) AS m(name, description, price, category, image_url)
WHERE r.name = 'US Pizza'
ON CONFLICT DO NOTHING;

-- ── Chat & Chill ─────────────────────────────────────────────────────────────
INSERT INTO menu_items (restaurant_id, name, description, price, category, image_url)
SELECT r.id, m.name, m.description, m.price, m.category, m.image_url
FROM restaurants r,
(VALUES
  ('Paneer Tikka Roll',   'Spiced paneer wrapped in a soft roti',        120, 'Rolls',      'https://images.unsplash.com/photo-1626700051175-6818013e1d4f?w=400&q=80'),
  ('Aloo Tikki',          'Crispy potato patties with chutneys',         60,  'Snacks',     'https://images.unsplash.com/photo-1601050690597-df0568f70950?w=400&q=80'),
  ('Samosa (2 pcs)',      'Flaky pastry stuffed with spiced potatoes',   40,  'Snacks',     'https://images.unsplash.com/photo-1601050690117-898bc9ce48ee?w=400&q=80'),
  ('Masala Chai',         'Freshly brewed spiced Indian tea',            30,  'Beverages',  'https://images.unsplash.com/photo-1571934811356-5cc061b6821f?w=400&q=80'),
  ('Cold Coffee',         'Chilled blended coffee with milk',            80,  'Beverages',  'https://images.unsplash.com/photo-1461023058943-07fcbe16d735?w=400&q=80')
) AS m(name, description, price, category, image_url)
WHERE r.name = 'Chat & Chill'
ON CONFLICT DO NOTHING;

-- ── Paradise ─────────────────────────────────────────────────────────────────
INSERT INTO menu_items (restaurant_id, name, description, price, category, image_url)
SELECT r.id, m.name, m.description, m.price, m.category, m.image_url
FROM restaurants r,
(VALUES
  ('Chicken Biryani',     'Fragrant basmati rice with tender chicken',   180, 'Biryani',    'https://images.unsplash.com/photo-1563379091339-03b21ab4a4f8?w=400&q=80'),
  ('Mutton Biryani',      'Slow-cooked mutton in aromatic spices',       220, 'Biryani',    'https://images.unsplash.com/photo-1589301760014-d929f3979dbc?w=400&q=80'),
  ('Veg Biryani',         'Garden vegetables in basmati rice',           140, 'Biryani',    'https://images.unsplash.com/photo-1596797038530-2c107229654b?w=400&q=80'),
  ('Raita',               'Cool yoghurt with cucumber and spices',       40,  'Sides',      'https://images.unsplash.com/photo-1571167366136-b57e39c45576?w=400&q=80'),
  ('Gulab Jamun',         'Soft milk dumplings in sugar syrup',          60,  'Desserts',   'https://images.unsplash.com/photo-1601050690117-898bc9ce48ee?w=400&q=80')
) AS m(name, description, price, category, image_url)
WHERE r.name = 'Paradise'
ON CONFLICT DO NOTHING;

-- ── Total Fresh ───────────────────────────────────────────────────────────────
INSERT INTO menu_items (restaurant_id, name, description, price, category, image_url)
SELECT r.id, m.name, m.description, m.price, m.category, m.image_url
FROM restaurants r,
(VALUES
  ('Fresh Lime Soda',     'Chilled lime with soda water and mint',       60,  'Beverages',  'https://images.unsplash.com/photo-1556679343-c7306c1976bc?w=400&q=80'),
  ('Watermelon Juice',    'Fresh pressed summer watermelon',             70,  'Beverages',  'https://images.unsplash.com/photo-1499638673689-79a0b5115d87?w=400&q=80'),
  ('Fruit Salad',         'Seasonal fruits with honey dressing',         90,  'Healthy',    'https://images.unsplash.com/photo-1490474418585-ba9bad8fd0ea?w=400&q=80'),
  ('Veg Sandwich',        'Multigrain bread with fresh veggies',         80,  'Healthy',    'https://images.unsplash.com/photo-1528735602780-2552fd46c7af?w=400&q=80'),
  ('Protein Smoothie',    'Banana, oat and peanut butter shake',         110, 'Beverages',  'https://images.unsplash.com/photo-1553530666-ba11a7da3888?w=400&q=80')
) AS m(name, description, price, category, image_url)
WHERE r.name = 'Total Fresh'
ON CONFLICT DO NOTHING;

-- ── Baskin Robbins ────────────────────────────────────────────────────────────
INSERT INTO menu_items (restaurant_id, name, description, price, category, image_url)
SELECT r.id, m.name, m.description, m.price, m.category, m.image_url
FROM restaurants r,
(VALUES
  ('Single Scoop',        'Any flavour from our 31 options',             80,  'Ice Cream',  'https://images.unsplash.com/photo-1497034825429-c343d7c6a68f?w=400&q=80'),
  ('Double Scoop',        'Two scoops of your choice',                   140, 'Ice Cream',  'https://images.unsplash.com/photo-1560008581-09826d1de69e?w=400&q=80'),
  ('Mississippi Mud Pie', 'Chocolate cake with ice cream layers',        160, 'Desserts',   'https://images.unsplash.com/photo-1606313564200-e75d5e30476c?w=400&q=80'),
  ('Cotton Candy Blast',  'Cotton candy ice cream in a waffle cone',     110, 'Ice Cream',  'https://images.unsplash.com/photo-1550617931-e17a7b70dce2?w=400&q=80'),
  ('Sundae',              'Vanilla ice cream with hot fudge sauce',      130, 'Desserts',   'https://images.unsplash.com/photo-1563805042-7684c019e1cb?w=400&q=80')
) AS m(name, description, price, category, image_url)
WHERE r.name = 'Baskin Robbins'
ON CONFLICT DO NOTHING;

-- ── Nescafe ───────────────────────────────────────────────────────────────────
INSERT INTO menu_items (restaurant_id, name, description, price, category, image_url)
SELECT r.id, m.name, m.description, m.price, m.category, m.image_url
FROM restaurants r,
(VALUES
  ('Cappuccino',          'Rich espresso with creamy steamed milk foam', 90,  'Coffee',     'https://images.unsplash.com/photo-1509042239860-f550ce710b93?w=400&q=80'),
  ('Latte',               'Smooth espresso with velvety milk',           85,  'Coffee',     'https://images.unsplash.com/photo-1461023058943-07fcbe16d735?w=400&q=80'),
  ('Cold Coffee',         'Chilled shaken coffee over ice',              80,  'Coffee',     'https://images.unsplash.com/photo-1555949258-eb67b1ef0ceb?w=400&q=80'),
  ('Veg Sandwich',        'Fresh veggies in toasted bread',              70,  'Snacks',     'https://images.unsplash.com/photo-1528735602780-2552fd46c7af?w=400&q=80'),
  ('Chocolate Muffin',    'Warm double-chocolate baked muffin',          60,  'Snacks',     'https://images.unsplash.com/photo-1607958996333-41aef7caefaa?w=400&q=80')
) AS m(name, description, price, category, image_url)
WHERE r.name = 'Nescafe'
ON CONFLICT DO NOTHING;

-- ---------------------------------------------------------------------------
-- HOME LOCATION RESERVATIONS (initialize all 5 as free)
-- ---------------------------------------------------------------------------
INSERT INTO home_location_reservations (location_id)
SELECT id FROM locations WHERE type = 'HOME'
ON CONFLICT (location_id) DO NOTHING;

-- ---------------------------------------------------------------------------
-- VERIFY SEED
-- ---------------------------------------------------------------------------
DO $$
DECLARE
  home_count  INT;
  rest_count  INT;
  block_count INT;
  menu_count  INT;
BEGIN
  SELECT COUNT(*) INTO home_count  FROM locations WHERE type = 'HOME';
  SELECT COUNT(*) INTO rest_count  FROM locations WHERE type = 'RESTAURANT';
  SELECT COUNT(*) INTO block_count FROM locations WHERE type = 'DELIVERY_BLOCK';
  SELECT COUNT(*) INTO menu_count  FROM menu_items;

  RAISE NOTICE '✅ Seed complete:';
  RAISE NOTICE '   HOME locations       : %', home_count;
  RAISE NOTICE '   RESTAURANT locations : %', rest_count;
  RAISE NOTICE '   DELIVERY_BLOCK locs  : %', block_count;
  RAISE NOTICE '   Menu items           : %', menu_count;

  IF home_count != 5 THEN
    RAISE EXCEPTION '❌ Expected 5 HOME locations, got %', home_count;
  END IF;
  IF rest_count != 7 THEN
    RAISE EXCEPTION '❌ Expected 7 RESTAURANT locations, got %', rest_count;
  END IF;
END $$;
