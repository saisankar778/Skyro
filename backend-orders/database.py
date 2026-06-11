import asyncpg
import sqlalchemy
import sqlalchemy.dialects.postgresql  # explicit import required for dialect access
from pathlib import Path
import os
import re as _re

# ─────────────────────────────────────────────────────────────────────────────
# DATABASE URL
#   Local dev  : sqlite (default, no config needed)
#   AWS RDS    : set DATABASE_URL=postgresql+asyncpg://user:pass@host:5432/skyro
# ─────────────────────────────────────────────────────────────────────────────
DB_PATH = (Path(__file__).parent / "orders.db").resolve()
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    f"sqlite:///{DB_PATH.as_posix()}"
)

_is_postgres = DATABASE_URL.startswith("postgresql")

# ─────────────────────────────────────────────────────────────────────────────
# DATABASE OBJECT — wraps either asyncpg pool (PostgreSQL) or databases/aiosqlite (SQLite)
# ─────────────────────────────────────────────────────────────────────────────
if _is_postgres:
    import re

    # Parse the URL manually for asyncpg (avoids ssl negotiation issues with databases lib)
    # Expected: postgresql+asyncpg://user:pass@host:port/db
    _url = DATABASE_URL.replace("postgresql+asyncpg://", "").replace("postgresql://", "")
    _match = re.match(r"([^:]+):([^@]+)@([^:/]+):?(\d+)?/([^?]+)", _url)
    if not _match:
        raise ValueError(f"Cannot parse DATABASE_URL: {DATABASE_URL}")

    _pg_user, _pg_pass, _pg_host, _pg_port, _pg_db = _match.groups()
    _pg_port = int(_pg_port or 5432)

    # Thin async wrapper that mimics the `databases` API used by crud.py
    import asyncio
    from typing import Any, List, Optional

    class _AsyncPGDatabase:
        """
        Drop-in replacement for `databases.Database` that uses asyncpg directly.
        Provides .fetch_all(), .fetch_one(), .execute(), .execute_many() async methods.
        """

        def __init__(self):
            self._pool: Optional[asyncpg.Pool] = None

        async def connect(self):
            import ssl
            ctx = ssl.create_default_context()
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE

            # Only use SSL context if we're connecting to an RDS instance or sslmode is requested
            use_ssl = ctx if "amazonaws.com" in _pg_host or "sslmode=require" in DATABASE_URL else False
            
            self._pool = await asyncpg.create_pool(
                host=_pg_host,
                port=_pg_port,
                user=_pg_user,
                password=_pg_pass,
                database=_pg_db,
                ssl=use_ssl,
                min_size=1,
                max_size=5,
            )

        async def disconnect(self):
            if self._pool:
                await self._pool.close()

        async def fetch_all(self, query) -> List[dict]:
            sql, params = _compile(query)
            async with self._pool.acquire() as conn:
                rows = await conn.fetch(sql, *params)
                return [dict(r) for r in rows]

        async def fetch_one(self, query) -> Optional[dict]:
            sql, params = _compile(query)
            async with self._pool.acquire() as conn:
                row = await conn.fetchrow(sql, *params)
                return dict(row) if row else None

        async def execute(self, query) -> Any:
            sql, params = _compile(query)
            async with self._pool.acquire() as conn:
                result = await conn.execute(sql, *params)
                # Try to return last inserted id or rowcount
                try:
                    return int(result.split()[-1])
                except Exception:
                    return result

        async def execute_many(self, query, values: List[dict]):
            sql, _ = _compile(query)
            # Build positional args lists for executemany
            if not values:
                return
            # We need column order — derive from first dict
            cols = list(values[0].keys())
            # Replace :colname with $N placeholders
            import re as _re
            sql_pg = sql
            for i, col in enumerate(cols, 1):
                sql_pg = _re.sub(rf":{col}\b", f"${i}", sql_pg)
            args_list = [tuple(row[c] for c in cols) for row in values]
            async with self._pool.acquire() as conn:
                await conn.executemany(sql_pg, args_list)

    def _compile(query) -> tuple:
        """
        Compile a SQLAlchemy query object to (sql_string, params_list).
        Handles PostgreSQL %(name)s placeholders → $1,$2,... for asyncpg.
        """
        from sqlalchemy.dialects.postgresql import dialect as PGDialect
        compiled = query.compile(
            dialect=PGDialect(),
            compile_kwargs={"literal_binds": False}
        )
        sql = str(compiled)
        params_dict = dict(compiled.params or {})

        # PostgreSQL dialect (psycopg2 style) generates %(name)s placeholders.
        # asyncpg requires positional $1, $2, ... placeholders.
        param_names = _re.findall(r'%\((\w+)\)s', sql)

        if not param_names:
            # Fallback for SA versions that emit :name style
            param_names = _re.findall(r':(\w+)', sql)
            seen, ordered_names = set(), []
            for n in param_names:
                if n not in seen:
                    seen.add(n)
                    ordered_names.append(n)
            for i, name in enumerate(ordered_names, 1):
                sql = _re.sub(rf':{name}\b', f'${i}', sql)
        else:
            seen, ordered_names = set(), []
            for n in param_names:
                if n not in seen:
                    seen.add(n)
                    ordered_names.append(n)
            for i, name in enumerate(ordered_names, 1):
                sql = sql.replace(f'%({name})s', f'${i}')

        params_list = [params_dict.get(n) for n in ordered_names]
        return sql, params_list

    database = _AsyncPGDatabase()

else:
    # SQLite local dev — keep original databases/aiosqlite approach
    import databases as _databases
    database = _databases.Database(DATABASE_URL)

metadata = sqlalchemy.MetaData()

# ─────────────────────────────────────────────────────────────────────────────
# ORDERS TABLE  — matches AWS RDS schema (schema.sql)
# ─────────────────────────────────────────────────────────────────────────────
orders = sqlalchemy.Table(
    "orders",
    metadata,
    sqlalchemy.Column("id",                  sqlalchemy.String,   primary_key=True),
    sqlalchemy.Column("legacy_id",           sqlalchemy.String,   nullable=True),   # ORD-<ts> from frontend
    sqlalchemy.Column("user_id",             sqlalchemy.String,   nullable=True),   # UUID of user
    sqlalchemy.Column("restaurant_id",       sqlalchemy.String,   nullable=True),
    sqlalchemy.Column("pickup_location_id",  sqlalchemy.String,   nullable=True),
    sqlalchemy.Column("drop_location_id",    sqlalchemy.String,   nullable=True),   # delivery location
    sqlalchemy.Column("status",              sqlalchemy.String,   nullable=False, server_default="CREATED"),
    sqlalchemy.Column("assigned_drone_id",   sqlalchemy.String,   nullable=True),
    sqlalchemy.Column("total_amount",        sqlalchemy.Numeric,  nullable=True),
    sqlalchemy.Column("created_at",          sqlalchemy.DateTime, server_default=sqlalchemy.func.now()),
    sqlalchemy.Column("updated_at",          sqlalchemy.DateTime, nullable=True),
    sqlalchemy.Column("completed_at",        sqlalchemy.DateTime, nullable=True),
)

# ─────────────────────────────────────────────────────────────────────────────
# ORDER ITEMS TABLE — matches AWS RDS schema (schema.sql)
# ─────────────────────────────────────────────────────────────────────────────
order_items = sqlalchemy.Table(
    "order_items",
    metadata,
    sqlalchemy.Column("id",             sqlalchemy.String,  primary_key=True),
    sqlalchemy.Column("order_id",       sqlalchemy.String,  sqlalchemy.ForeignKey("orders.id", ondelete="CASCADE"), nullable=False),
    sqlalchemy.Column("menu_item_id",   sqlalchemy.String,  nullable=True),
    sqlalchemy.Column("item_name",      sqlalchemy.String,  nullable=True),   # denormalized name
    sqlalchemy.Column("quantity",       sqlalchemy.Integer, nullable=False),
    sqlalchemy.Column("price_at_time",  sqlalchemy.Numeric, nullable=False),  # price when ordered
)

# ─────────────────────────────────────────────────────────────────────────────
# LOCATIONS TABLES
# ─────────────────────────────────────────────────────────────────────────────
locations = sqlalchemy.Table(
    "locations",
    metadata,
    sqlalchemy.Column("id", sqlalchemy.String, primary_key=True),
    sqlalchemy.Column("name", sqlalchemy.String, unique=True, nullable=False),
    sqlalchemy.Column("type", sqlalchemy.String, nullable=False),
    sqlalchemy.Column("latitude", sqlalchemy.Float, nullable=False),
    sqlalchemy.Column("longitude", sqlalchemy.Float, nullable=False),
    sqlalchemy.Column("is_active", sqlalchemy.Boolean, server_default="true"),
    schema=None
)

home_location_reservations = sqlalchemy.Table(
    "home_location_reservations",
    metadata,
    sqlalchemy.Column("location_id", sqlalchemy.String, sqlalchemy.ForeignKey("locations.id"), primary_key=True),
    sqlalchemy.Column("is_reserved", sqlalchemy.Boolean, server_default="false"),
    sqlalchemy.Column("reserved_by_drone", sqlalchemy.String, nullable=True),
    sqlalchemy.Column("reserved_at", sqlalchemy.DateTime, nullable=True),
    sqlalchemy.Column("released_at", sqlalchemy.DateTime, nullable=True),
    schema=None
)

# ─────────────────────────────────────────────────────────────────────────────
# RESTAURANTS TABLE
# ─────────────────────────────────────────────────────────────────────────────
restaurants = sqlalchemy.Table(
    "restaurants",
    metadata,
    sqlalchemy.Column("id",                sqlalchemy.String,  primary_key=True),
    sqlalchemy.Column("name",              sqlalchemy.String,  nullable=False),
    sqlalchemy.Column("tagline",           sqlalchemy.String,  nullable=True),
    sqlalchemy.Column("rating",            sqlalchemy.Float,   server_default="0"),
    sqlalchemy.Column("location_id",       sqlalchemy.String,  sqlalchemy.ForeignKey("locations.id"), nullable=False),
    sqlalchemy.Column("is_active",         sqlalchemy.Boolean, server_default="true"),
    sqlalchemy.Column("cuisine",           sqlalchemy.String,  nullable=True),
    sqlalchemy.Column("delivery_time_min", sqlalchemy.Integer, server_default="20"),
    sqlalchemy.Column("price_for_two",     sqlalchemy.Integer, server_default="300"),
    sqlalchemy.Column("offer",             sqlalchemy.String,  nullable=True),
    sqlalchemy.Column("image_url",         sqlalchemy.String,  nullable=True),
    schema=None
)

# ─────────────────────────────────────────────────────────────────────────────
# MENU ITEMS TABLE
# ─────────────────────────────────────────────────────────────────────────────
menu_items = sqlalchemy.Table(
    "menu_items",
    metadata,
    sqlalchemy.Column("id",            sqlalchemy.String,  primary_key=True),
    sqlalchemy.Column("restaurant_id", sqlalchemy.String,  sqlalchemy.ForeignKey("restaurants.id", ondelete="CASCADE"), nullable=False),
    sqlalchemy.Column("name",          sqlalchemy.String,  nullable=False),
    sqlalchemy.Column("description",   sqlalchemy.String,  nullable=True),
    sqlalchemy.Column("price",         sqlalchemy.Float,   nullable=False),
    sqlalchemy.Column("category",      sqlalchemy.String,  nullable=True),
    sqlalchemy.Column("image_url",     sqlalchemy.String,  nullable=True),
    sqlalchemy.Column("is_available",  sqlalchemy.Boolean, server_default="true"),
    sqlalchemy.Column("is_veg",        sqlalchemy.Boolean, server_default="false"),   # 🟢 veg/non-veg flag
    sqlalchemy.Column("weight_grams",  sqlalchemy.Integer, server_default="300"),     # ⚖️ drone payload weight
    schema=None
)

# ─────────────────────────────────────────────────────────────────────────────
food_categories = sqlalchemy.Table(
    "food_categories",
    metadata,
    sqlalchemy.Column("id",         sqlalchemy.String, primary_key=True),
    sqlalchemy.Column("name",       sqlalchemy.String, nullable=False, unique=True),
    sqlalchemy.Column("emoji",      sqlalchemy.String, server_default="🍽️"),
    sqlalchemy.Column("sort_order", sqlalchemy.Integer, server_default="0"),
    schema=None
)

# ─────────────────────────────────────────────────────────────────────────────
# SYNC ENGINE — SQLite only (PostgreSQL tables managed by db/migrate.py)
# ─────────────────────────────────────────────────────────────────────────────
if not _is_postgres:
    SYNC_DATABASE_URL = DATABASE_URL.replace("+aiosqlite", "")
    engine = sqlalchemy.create_engine(SYNC_DATABASE_URL, connect_args={"check_same_thread": False})
    metadata.create_all(engine)
