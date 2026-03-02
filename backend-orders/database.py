import databases
import sqlalchemy
from pathlib import Path
import os

DB_PATH = (Path(__file__).parent / "orders.db").resolve()
# Prefer env-provided DATABASE_URL (e.g., Postgres on cloud). Fallback to local SQLite file.
DATABASE_URL = os.getenv("DATABASE_URL", f"sqlite:///{DB_PATH.as_posix()}")  # e.g., postgresql://user:pass@host:5432/db

database = databases.Database(DATABASE_URL)
metadata = sqlalchemy.MetaData()

orders = sqlalchemy.Table(
    "orders",
    metadata,
    # Match frontend's string order IDs like ORD-<timestamp>
    sqlalchemy.Column("id", sqlalchemy.String, primary_key=True),
    sqlalchemy.Column("user", sqlalchemy.String, nullable=False),
    sqlalchemy.Column("restaurant_id", sqlalchemy.String, nullable=False),
    sqlalchemy.Column("total", sqlalchemy.Float, nullable=False),
    sqlalchemy.Column("delivery_location_id", sqlalchemy.String, nullable=False),
    sqlalchemy.Column("status", sqlalchemy.String, nullable=False, server_default="Placed"),
    sqlalchemy.Column("created_at", sqlalchemy.DateTime, server_default=sqlalchemy.func.now(), nullable=False),
    sqlalchemy.Column("drone_id", sqlalchemy.String, nullable=True),
)

order_items = sqlalchemy.Table(
    "order_items",
    metadata,
    sqlalchemy.Column("id", sqlalchemy.Integer, primary_key=True, autoincrement=True),
    sqlalchemy.Column("order_id", sqlalchemy.String, sqlalchemy.ForeignKey("orders.id", ondelete="CASCADE"), nullable=False),
    sqlalchemy.Column("item_id", sqlalchemy.String, nullable=False),
    sqlalchemy.Column("name", sqlalchemy.String, nullable=False),
    sqlalchemy.Column("price", sqlalchemy.Float, nullable=False),
    sqlalchemy.Column("quantity", sqlalchemy.Integer, nullable=False),
    sqlalchemy.Column("restaurant_id", sqlalchemy.String, nullable=False),
)

# For metadata.create_all, we need a synchronous engine.
# If DATABASE_URL is set to use aiosqlite (async), we must strip it for the sync engine.
SYNC_DATABASE_URL = DATABASE_URL.replace("+aiosqlite", "")

connect_args = {"check_same_thread": False} if SYNC_DATABASE_URL.startswith("sqlite") else {}
engine = sqlalchemy.create_engine(SYNC_DATABASE_URL, connect_args=connect_args)
metadata.create_all(engine)
