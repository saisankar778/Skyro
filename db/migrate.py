#!/usr/bin/env python3
"""
db/migrate.py -- Skyro Production Database Migration Script

Usage:
    python migrate.py
    DATABASE_URL=postgresql://user:pass@host:5432/skyro python migrate.py

Options:
    --schema-only   Run schema.sql only (skip seed)
    --seed-only     Run seed.sql only (skip schema)
    --reset         DROP and recreate all tables (DANGER: destroys data)
"""

import os
import sys
import argparse
from pathlib import Path

# Force UTF-8 output on Windows so emoji in SQL don't crash the script
if hasattr(sys.stdout, 'buffer'):
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

DB_DIR = Path(__file__).parent


def get_connection_url() -> str:
    url = os.getenv(
        "DATABASE_URL",
        "postgresql://skyro_admin:local_dev_pass@localhost:5432/skyro"
    )
    return url.replace("+asyncpg", "").replace("+aiosqlite", "")


def run_sql_file(conn, filepath: Path, label: str) -> None:
    sql = filepath.read_text(encoding="utf-8")
    print(f"\n{'─'*60}")
    print(f"  Running: {label}")
    print(f"{'─'*60}")
    conn.execute(sql)
    print(f"  [OK] {label} done")


def check_tables(conn) -> None:
    result = conn.execute("""
        SELECT table_name
        FROM information_schema.tables
        WHERE table_schema = 'public'
        ORDER BY table_name;
    """).fetchall()
    print(f"\n{'─'*60}")
    print("  Tables in database:")
    for row in result:
        print(f"    - {row[0]}")


def check_locations(conn) -> None:
    result = conn.execute("""
        SELECT type, COUNT(*) as count
        FROM locations
        GROUP BY type
        ORDER BY type;
    """).fetchall()
    print("\n  Location counts:")
    for row in result:
        print(f"    - {row[0]:<18}: {row[1]} records")

    home_result = conn.execute("""
        SELECT l.name, l.latitude, l.longitude,
               COALESCE(r.is_reserved, FALSE) as is_reserved
        FROM locations l
        LEFT JOIN home_location_reservations r ON r.location_id = l.id
        WHERE l.type = 'HOME'
        ORDER BY l.name;
    """).fetchall()

    print("\n  Home Location Status:")
    for row in home_result:
        status = "[RESERVED]" if row[3] else "[FREE]"
        print(f"    - {row[0]:<12}  ({row[1]:.6f}, {row[2]:.6f})  {status}")

    menu_result = conn.execute("""
        SELECT r.name, COUNT(m.id) as item_count
        FROM restaurants r
        LEFT JOIN menu_items m ON m.restaurant_id = r.id
        GROUP BY r.name ORDER BY r.name;
    """).fetchall()
    print("\n  Menu items per restaurant:")
    for row in menu_result:
        print(f"    - {row[0]:<20}: {row[1]} items")


def main():
    parser = argparse.ArgumentParser(description="Skyro DB Migration")
    parser.add_argument("--schema-only", action="store_true")
    parser.add_argument("--seed-only",   action="store_true")
    parser.add_argument("--reset",       action="store_true",
                        help="DROP all tables and recreate (DESTROYS DATA)")
    args = parser.parse_args()

    try:
        import psycopg2
        from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT
    except ImportError:
        print("ERROR: psycopg2 not installed. Run: pip install psycopg2-binary")
        sys.exit(1)

    url = get_connection_url()
    print("\nSkyro DB Migration")
    print(f"   Connecting to: {url[:url.rfind('@')+1]}***")

    try:
        conn = psycopg2.connect(url)
        conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
        cur = conn.cursor()
    except Exception as e:
        print(f"\nERROR: Connection failed: {e}")
        print("\nTips:")
        print("  - For local dev: docker-compose up postgres")
        print("  - Set DATABASE_URL env for AWS RDS")
        sys.exit(1)

    class _Executor:
        def __init__(self, cursor): self._cur = cursor
        def execute(self, sql):
            self._cur.execute(sql)
            return self
        def fetchall(self): return self._cur.fetchall()

    executor = _Executor(cur)

    if args.reset:
        print("\nWARNING: RESET MODE -- dropping all Skyro tables in 3 seconds...")
        import time; time.sleep(3)
        cur.execute("""
            DROP TABLE IF EXISTS
                system_events, home_location_reservations,
                delivery_missions, order_items, orders,
                menu_items, restaurants, drones, users, locations
            CASCADE;
            DROP TYPE IF EXISTS location_type, order_status, drone_status, mission_status CASCADE;
        """)
        print("  [OK] Reset complete")

    if not args.seed_only:
        run_sql_file(executor, DB_DIR / "schema.sql", "schema.sql")

    if not args.schema_only:
        run_sql_file(executor, DB_DIR / "seed.sql",   "seed.sql")

    print(f"\n{'─'*60}")
    print("  Migration complete -- verifying...")
    check_tables(executor)
    check_locations(executor)

    cur.close()
    conn.close()
    print(f"\n{'─'*60}")
    print("  Database is ready!\n")


if __name__ == "__main__":
    main()
