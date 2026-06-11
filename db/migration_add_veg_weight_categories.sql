-- =============================================================================
-- SKYRO — MIGRATION: Add is_veg, weight_grams, food_categories
-- Run against your RDS PostgreSQL database:
--   psql $DATABASE_URL -f db/migration_add_veg_weight_categories.sql
--
-- Safe to run multiple times (all statements are idempotent).
-- =============================================================================

-- ---------------------------------------------------------------------------
-- 1. Add new columns to menu_items
-- ---------------------------------------------------------------------------
ALTER TABLE menu_items
    ADD COLUMN IF NOT EXISTS is_veg       BOOLEAN  DEFAULT FALSE;

ALTER TABLE menu_items
    ADD COLUMN IF NOT EXISTS weight_grams INTEGER  DEFAULT 300;

-- ---------------------------------------------------------------------------
-- 2. Create food_categories table
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS food_categories (
    id          UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name        VARCHAR(50) UNIQUE NOT NULL,
    emoji       VARCHAR(10) DEFAULT '🍽️',
    sort_order  INT DEFAULT 0
);

-- ---------------------------------------------------------------------------
-- 3. Seed food_categories (real data — drives Home Screen filter pills)
-- ---------------------------------------------------------------------------
INSERT INTO food_categories (name, emoji, sort_order) VALUES
    ('All',        '🍽️', 0),
    ('Pizza',      '🍕', 1),
    ('Biryani',    '🍛', 2),
    ('Snacks',     '🥪', 3),
    ('Beverages',  '🥤', 4),
    ('Desserts',   '🍨', 5),
    ('Healthy',    '🥗', 6),
    ('Coffee',     '☕', 7),
    ('Ice Cream',  '🍦', 8)
ON CONFLICT (name) DO UPDATE
    SET emoji = EXCLUDED.emoji,
        sort_order = EXCLUDED.sort_order;

-- ---------------------------------------------------------------------------
-- 4. Update is_veg for existing menu items
--    Rule: item is vegetarian if it contains no chicken/mutton/prawn/fish/egg
-- ---------------------------------------------------------------------------

-- ── Dominos (all veg) ────────────────────────────────────────────────────────
UPDATE menu_items SET is_veg = TRUE
WHERE name IN ('Farmhouse Pizza', 'Peppy Paneer', 'Margherita', 'Garlic Bread', 'Choco Lava Cake');

-- ── US Pizza ─────────────────────────────────────────────────────────────────
UPDATE menu_items SET is_veg = FALSE WHERE name IN ('BBQ Chicken Pizza');
UPDATE menu_items SET is_veg = TRUE  WHERE name IN ('Double Cheese Pizza', 'Stuffed Crust Pizza', 'Pasta Arrabiata', 'Garlic Dip');

-- ── Chat & Chill (mostly veg) ─────────────────────────────────────────────────
UPDATE menu_items SET is_veg = TRUE
WHERE name IN ('Paneer Tikka Roll', 'Aloo Tikki', 'Samosa (2 pcs)', 'Masala Chai', 'Cold Coffee');

-- ── Paradise ─────────────────────────────────────────────────────────────────
UPDATE menu_items SET is_veg = FALSE WHERE name IN ('Chicken Biryani', 'Mutton Biryani');
UPDATE menu_items SET is_veg = TRUE  WHERE name IN ('Veg Biryani', 'Raita', 'Gulab Jamun');

-- ── Total Fresh (all veg) ─────────────────────────────────────────────────────
UPDATE menu_items SET is_veg = TRUE
WHERE name IN ('Fresh Lime Soda', 'Watermelon Juice', 'Fruit Salad', 'Veg Sandwich', 'Protein Smoothie');

-- ── Baskin Robbins (all veg) ─────────────────────────────────────────────────
UPDATE menu_items SET is_veg = TRUE
WHERE name IN ('Single Scoop', 'Double Scoop', 'Mississippi Mud Pie', 'Cotton Candy Blast', 'Sundae');

-- ── Nescafe (all veg) ────────────────────────────────────────────────────────
UPDATE menu_items SET is_veg = TRUE
WHERE name IN ('Cappuccino', 'Latte', 'Cold Coffee', 'Veg Sandwich', 'Chocolate Muffin');

-- ---------------------------------------------------------------------------
-- 5. Update weight_grams for existing menu items
--    Realistic drone payload weights based on food type
-- ---------------------------------------------------------------------------

-- Pizzas (medium box ~500g)
UPDATE menu_items SET weight_grams = 520 WHERE name IN ('Farmhouse Pizza', 'Peppy Paneer', 'Margherita');
UPDATE menu_items SET weight_grams = 540 WHERE name IN ('Double Cheese Pizza', 'BBQ Chicken Pizza', 'Stuffed Crust Pizza');

-- Biryani boxes
UPDATE menu_items SET weight_grams = 400 WHERE name IN ('Chicken Biryani', 'Mutton Biryani', 'Veg Biryani');

-- Snacks / rolls / light items
UPDATE menu_items SET weight_grams = 180 WHERE name IN ('Paneer Tikka Roll');
UPDATE menu_items SET weight_grams = 120 WHERE name IN ('Aloo Tikki', 'Samosa (2 pcs)');
UPDATE menu_items SET weight_grams = 150 WHERE name IN ('Garlic Bread');
UPDATE menu_items SET weight_grams = 200 WHERE name IN ('Pasta Arrabiata');

-- Beverages (350ml cup)
UPDATE menu_items SET weight_grams = 380 WHERE name IN ('Masala Chai', 'Cold Coffee', 'Fresh Lime Soda', 'Watermelon Juice', 'Protein Smoothie');
UPDATE menu_items SET weight_grams = 350 WHERE name IN ('Cappuccino', 'Latte');

-- Desserts / ice cream (per portion)
UPDATE menu_items SET weight_grams = 200 WHERE name IN ('Choco Lava Cake', 'Mississippi Mud Pie', 'Gulab Jamun');
UPDATE menu_items SET weight_grams = 150 WHERE name IN ('Single Scoop', 'Sundae');
UPDATE menu_items SET weight_grams = 250 WHERE name IN ('Double Scoop', 'Cotton Candy Blast');
UPDATE menu_items SET weight_grams = 80  WHERE name IN ('Garlic Dip');
UPDATE menu_items SET weight_grams = 90  WHERE name IN ('Raita');
UPDATE menu_items SET weight_grams = 100 WHERE name IN ('Chocolate Muffin');

-- Light snacks / sides
UPDATE menu_items SET weight_grams = 140 WHERE name IN ('Veg Sandwich', 'Fruit Salad');

-- ---------------------------------------------------------------------------
-- 6. Verify migration
-- ---------------------------------------------------------------------------
DO $$
DECLARE
    veg_count    INT;
    nonveg_count INT;
    wt_default   INT;
    cat_count    INT;
BEGIN
    SELECT COUNT(*) INTO veg_count    FROM menu_items WHERE is_veg = TRUE;
    SELECT COUNT(*) INTO nonveg_count FROM menu_items WHERE is_veg = FALSE;
    SELECT COUNT(*) INTO wt_default   FROM menu_items WHERE weight_grams = 300;
    SELECT COUNT(*) INTO cat_count    FROM food_categories;

    RAISE NOTICE '✅ Migration complete:';
    RAISE NOTICE '   Veg items          : %', veg_count;
    RAISE NOTICE '   Non-veg items      : %', nonveg_count;
    RAISE NOTICE '   Items at 300g default: %', wt_default;
    RAISE NOTICE '   Food categories    : %', cat_count;
END $$;
