from typing import List, Dict, Any, Optional
from database import database, orders, order_items
import schemas
from events import broadcast
import time
import uuid as _uuid_mod


def _coerce_uuid(value: Optional[str]) -> Optional[str]:
    """Return value if it is a valid UUID string, otherwise None.
    Prevents asyncpg DataError when the frontend sends non-UUID user identifiers
    like 'demo_user' into a UUID column.
    """
    if not value:
        return None
    try:
        _uuid_mod.UUID(str(value))
        return str(value)
    except (ValueError, AttributeError):
        return None


# Maps PostgreSQL order_status enum values → frontend OrderStatus labels
_DB_STATUS_TO_FRONTEND = {
    "CREATED":           "Placed",
    "CONFIRMED":         "Accepted",
    "PREPARING":         "Cooking",
    "READY_FOR_PICKUP":  "Ready for Launch",
    "DRONE_ASSIGNED":    "En Route",
    "IN_FLIGHT":         "En Route",
    "DELIVERED":         "Delivered",
    "FAILED":            "Failed",
    "CANCELLED":         "Declined",
    # Frontend values pass through unchanged (idempotent)
    "Placed":            "Placed",
    "Declined":          "Declined",
    "Accepted":          "Accepted",
    "Cooking":           "Cooking",
    "Ready for Launch":  "Ready for Launch",
    "En Route":          "En Route",
    "Delivered":         "Delivered",
    "Failed":            "Failed",
    # Uppercase variations from mobile client
    "PLACED":            "Placed",
    "ACCEPTED":          "Accepted",
    "COOKING":           "Cooking",
    "READY_FOR_LAUNCH":  "Ready for Launch",
    "IN_FLIGHT_UPPER":   "En Route",
    "IN_FLIGHT":         "En Route",
    "ARRIVED":           "Delivered",
    "DELIVERED_UPPER":   "Delivered",
    "DECLINED_UPPER":    "Declined",
    "FAILED_UPPER":      "Failed",
}

# Maps frontend OrderStatus labels → PostgreSQL order_status enum values
_FRONTEND_STATUS_TO_DB = {
    "Placed":           "CREATED",
    "Accepted":         "CONFIRMED",
    "Cooking":          "PREPARING",
    "Ready for Launch": "READY_FOR_PICKUP",
    "En Route":         "IN_FLIGHT",
    "Delivered":        "DELIVERED",
    "Failed":           "FAILED",
    "Declined":         "CANCELLED",
    # DB values pass through unchanged (idempotent)
    "CREATED":          "CREATED",
    "CONFIRMED":        "CONFIRMED",
    "PREPARING":        "PREPARING",
    "READY_FOR_PICKUP": "READY_FOR_PICKUP",
    "DRONE_ASSIGNED":   "DRONE_ASSIGNED",
    "IN_FLIGHT":        "IN_FLIGHT",
    "DELIVERED":        "DELIVERED",
    "FAILED":           "FAILED",
    "CANCELLED":        "CANCELLED",
    # Uppercase client values
    "PLACED":           "CREATED",
    "ACCEPTED":         "CONFIRMED",
    "COOKING":          "PREPARING",
    "READY_FOR_LAUNCH": "READY_FOR_PICKUP",
    "IN_FLIGHT_UPPER":  "IN_FLIGHT",
    "ARRIVED":          "DELIVERED",
    "DELIVERED_UPPER":  "DELIVERED",
    "DECLINED_UPPER":   "CANCELLED",
    "FAILED_UPPER":     "FAILED",
}



def _map_status(raw: str) -> str:
    """Translate a DB or frontend status string to a valid frontend OrderStatus."""
    return _DB_STATUS_TO_FRONTEND.get(str(raw), "Placed")


def _map_status_to_db(raw: str) -> str:
    """Translate a frontend or DB status string to a valid PostgreSQL order_status."""
    return _FRONTEND_STATUS_TO_DB.get(str(raw), "CREATED")


def _serialize_order(order_row: Dict[str, Any], items_rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Map AWS RDS DB rows → frontend's Order shape (camelCase)."""
    return {
        # Use legacy_id (ORD-<ts>) as the display id if available, else UUID
        "id": order_row.get("legacy_id") or str(order_row["id"]),
        "user": order_row.get("user_id") or "",
        "restaurantId": str(order_row["restaurant_id"]) if order_row.get("restaurant_id") else "",
        "items": [
            {
                "id": str(it.get("menu_item_id") or it.get("id")),
                "name": it.get("item_name") or "",
                "price": float(it.get("price_at_time") or 0),
                "quantity": int(it.get("quantity") or 1),
                "restaurantId": str(order_row["restaurant_id"]) if order_row.get("restaurant_id") else "",
            }
            for it in items_rows
        ],
        "total": float(order_row.get("total_amount") or 0),
        "deliveryLocationId": str(order_row.get("drop_location_id") or ""),
        "status": _map_status(order_row.get("status") or "CREATED"),
        "createdAt": (
            order_row["created_at"].isoformat()
            if getattr(order_row.get("created_at"), "isoformat", None)
            else str(order_row.get("created_at") or "")
        ),
        "droneId": order_row.get("assigned_drone_id"),
        "assigned_drone_id": order_row.get("assigned_drone_id"),
    }


async def _fetch_order_with_items(order_id: str) -> Dict[str, Any]:
    """Fetch by UUID or legacy_id.

    asyncpg will raise DataError if a non-UUID string (e.g. 'ORD-1777139079395')
    is passed to a UUID column. We validate first and only query by `id` when
    the string is a genuine UUID; otherwise go straight to `legacy_id`.
    """
    import sqlalchemy as sa
    order_row = None
    # Only query the UUID primary-key column if order_id is actually a UUID
    if _coerce_uuid(order_id):
        order_row = await database.fetch_one(orders.select().where(orders.c.id == order_id))
    # Fall back to the legacy ORD-<timestamp> string column
    if not order_row:
        order_row = await database.fetch_one(orders.select().where(orders.c.legacy_id == order_id))
    if not order_row:
        return None
    real_uuid = str(order_row["id"])
    items_rows = await database.fetch_all(
        order_items.select().where(order_items.c.order_id == real_uuid)
    )
    return _serialize_order(dict(order_row), [dict(r) for r in items_rows])


async def create_order(order: schemas.OrderCreate):
    # Generate a UUID for the DB primary key
    new_uuid = str(_uuid_mod.uuid4())
    # Store the legacy ORD-<ts> string as legacy_id for frontend compatibility
    legacy_id = order.id or f"ORD-{int(time.time() * 1000)}"

    # All FK columns are UUID in PostgreSQL. The frontend may send non-UUID
    # strings (e.g. "Dominos", "demo_user"). _coerce_uuid() returns None for
    # anything that isn't a valid UUID, preventing asyncpg DataError crashes.
    await database.execute(
        orders.insert().values(
            id=new_uuid,
            legacy_id=legacy_id,
            user_id=_coerce_uuid(order.user),
            restaurant_id=_coerce_uuid(order.restaurantId),
            total_amount=order.total,
            drop_location_id=_coerce_uuid(order.deliveryLocationId),
            status="CREATED",
            assigned_drone_id=None,
        )
    )

    # Insert items
    if order.items:
        values = [
            {
                "id": str(_uuid_mod.uuid4()),
                "order_id": new_uuid,
                "menu_item_id": _coerce_uuid(it.id),   # may be a name string
                "item_name": it.name,
                "quantity": it.quantity,
                "price_at_time": it.price,
            }
            for it in order.items
        ]
        await database.execute_many(order_items.insert(), values)

    full_order = await _fetch_order_with_items(new_uuid)

    await broadcast({"event": "order_created", "order": full_order})
    return full_order


async def get_orders() -> List[Dict[str, Any]]:
    rows = await database.fetch_all(orders.select().order_by(orders.c.created_at.desc()))
    results: List[Dict[str, Any]] = []
    for row in rows:
        results.append(await _fetch_order_with_items(str(row["id"])))
    return results


async def get_order(order_id: str) -> Dict[str, Any]:
    return await _fetch_order_with_items(order_id)


async def update_order(order_id: str, payload: schemas.OrderUpdate):
    import sqlalchemy as sa

    # Find the real UUID — guard against non-UUID legacy IDs (e.g. ORD-<ts>)
    order_row = None
    if _coerce_uuid(order_id):
        order_row = await database.fetch_one(orders.select().where(orders.c.id == order_id))
    if not order_row:
        order_row = await database.fetch_one(orders.select().where(orders.c.legacy_id == order_id))
    if not order_row:
        return None

    real_uuid = str(order_row["id"])
    values = {}
    if payload.status is not None:
        raw = payload.status.value if hasattr(payload.status, "value") else payload.status
        values["status"] = _map_status_to_db(raw)  # translate frontend label → DB enum
    if payload.droneId is not None:
        values["assigned_drone_id"] = payload.droneId
    if payload.assigned_drone_id is not None:
        values["assigned_drone_id"] = payload.assigned_drone_id

    if values:
        await database.execute(orders.update().where(orders.c.id == real_uuid).values(**values))

    full_order = await _fetch_order_with_items(real_uuid)
    if full_order:
        await broadcast({"event": "order_updated", "order": full_order})
    return full_order


async def assign_drone_to_order(order_id: str, drone_id: str):
    import sqlalchemy as sa

    # Resolve to UUID — guard against non-UUID legacy IDs (e.g. ORD-<ts>)
    order_row = None
    if _coerce_uuid(order_id):
        order_row = await database.fetch_one(orders.select().where(orders.c.id == order_id))
    if not order_row:
        order_row = await database.fetch_one(orders.select().where(orders.c.legacy_id == order_id))
    if not order_row:
        return None

    real_uuid = str(order_row["id"])
    query = (
        orders.update()
        .where(sa.and_(
            orders.c.id == real_uuid,
            orders.c.assigned_drone_id == None,  # noqa: E711
        ))
        .values(
            assigned_drone_id=drone_id,
            status="DRONE_ASSIGNED",
        )
    )
    await database.execute(query)

    full_order = await _fetch_order_with_items(real_uuid)
    if full_order is None:
        return None
    if full_order.get("assigned_drone_id") != drone_id:
        return None  # race condition — another drone won

    await broadcast({"event": "order_assigned", "order": full_order})
    return full_order


# ─────────────────────────────────────────────────────────────────────────────
# LOCATIONS (Fleet AI integration)
# ─────────────────────────────────────────────────────────────────────────────

async def get_locations(type_filter: str = None) -> List[Dict[str, Any]]:
    from database import locations
    import sqlalchemy as sa

    query = sa.select(
        sa.cast(locations.c.id, sa.String).label("id"),
        locations.c.name,
        sa.cast(locations.c.type, sa.String).label("type"),
        locations.c.latitude,
        locations.c.longitude,
        locations.c.is_active,
    )
    if type_filter:
        query = query.where(sa.cast(locations.c.type, sa.String) == type_filter)
    query = query.order_by(locations.c.name)
    rows = await database.fetch_all(query)
    return [dict(row) for row in rows]


async def upsert_home_reservation(zone: str, drone_id: str, reserved: bool):
    import sqlalchemy as sa
    from database import locations, home_location_reservations
    from datetime import datetime

    loc = await database.fetch_one(locations.select().where(locations.c.name == zone))
    if not loc:
        return None

    loc_id = str(loc["id"])
    query = (
        home_location_reservations.update()
        .where(home_location_reservations.c.location_id == loc_id)
        .values(
            is_reserved=reserved,
            reserved_by_drone=drone_id if reserved else None,
            reserved_at=datetime.utcnow() if reserved else None,
            released_at=None if reserved else datetime.utcnow(),
        )
    )
    await database.execute(query)
    return True


# ─────────────────────────────────────────────────────────────────────────────
# RESTAURANTS & MENU ITEMS (frontend catalogue)
# ─────────────────────────────────────────────────────────────────────────────

async def get_restaurants() -> List[Dict[str, Any]]:
    from database import restaurants, locations
    import sqlalchemy as sa

    query = (
        sa.select(
            sa.cast(restaurants.c.id, sa.String).label("id"),
            restaurants.c.name,
            restaurants.c.tagline,
            restaurants.c.rating,
            restaurants.c.cuisine,
            restaurants.c.delivery_time_min,
            restaurants.c.price_for_two,
            restaurants.c.offer,
            restaurants.c.image_url,
            restaurants.c.is_active,
            locations.c.latitude,
            locations.c.longitude,
        )
        .select_from(restaurants.join(locations, sa.cast(restaurants.c.location_id, sa.String) == sa.cast(locations.c.id, sa.String)))
        .where(restaurants.c.is_active == True)  # noqa: E712
        .order_by(restaurants.c.name)
    )
    rows = await database.fetch_all(query)
    return [dict(row) for row in rows]


async def get_menu_items(restaurant_id: str = None) -> List[Dict[str, Any]]:
    from database import menu_items
    import sqlalchemy as sa

    query = sa.select(
        sa.cast(menu_items.c.id, sa.String).label("id"),
        sa.cast(menu_items.c.restaurant_id, sa.String).label("restaurant_id"),
        menu_items.c.name,
        menu_items.c.description,
        menu_items.c.price,
        menu_items.c.category,
        menu_items.c.image_url,
        menu_items.c.is_available,
        menu_items.c.is_veg,
        menu_items.c.weight_grams,
    ).where(menu_items.c.is_available == True)  # noqa: E712
    if restaurant_id:
        query = query.where(sa.cast(menu_items.c.restaurant_id, sa.String) == str(restaurant_id))
    query = query.order_by(menu_items.c.category, menu_items.c.name)
    rows = await database.fetch_all(query)
    return [dict(row) for row in rows]


async def get_categories() -> List[Dict[str, Any]]:
    """Return all food categories ordered by sort_order."""
    from database import food_categories
    import sqlalchemy as sa

    query = sa.select(
        sa.cast(food_categories.c.id, sa.String).label("id"),
        food_categories.c.name,
        food_categories.c.emoji,
        food_categories.c.sort_order,
    ).order_by(food_categories.c.sort_order)
    rows = await database.fetch_all(query)
    return [dict(row) for row in rows]
