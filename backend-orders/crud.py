from typing import List, Dict, Any
from database import database, orders, order_items
import schemas
from events import broadcast
import time


def _serialize_order(order_row: Dict[str, Any], items_rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Map DB rows to frontend's Order shape (camelCase fields and nested items)."""
    return {
        "id": order_row["id"],
        "user": order_row["user"],
        "restaurantId": order_row["restaurant_id"],
        "items": [
            {
                "id": it["item_id"],
                "name": it["name"],
                "price": float(it["price"]),
                "quantity": int(it["quantity"]),
                "restaurantId": it["restaurant_id"],
            }
            for it in items_rows
        ],
        "total": float(order_row["total"]),
        "deliveryLocationId": order_row["delivery_location_id"],
        "status": order_row["status"],
        # Return ISO string for createdAt
        "createdAt": (
            order_row["created_at"].isoformat() if getattr(order_row["created_at"], "isoformat", None) else str(order_row["created_at"])  # sqlite may return str
        ),
        "droneId": order_row["drone_id"],
    }


async def _fetch_order_with_items(order_id: str) -> Dict[str, Any]:
    order_row = await database.fetch_one(orders.select().where(orders.c.id == order_id))
    if not order_row:
        return None
    items_rows = await database.fetch_all(
        order_items.select().where(order_items.c.order_id == order_id)
    )
    return _serialize_order(dict(order_row), [dict(r) for r in items_rows])


async def create_order(order: schemas.OrderCreate):
    # Use provided id or generate ORD-<ts>
    order_id = order.id or f"ORD-{int(time.time() * 1000)}"

    # Insert into orders table
    await database.execute(
        orders.insert().values(
            id=order_id,
            user=order.user,
            restaurant_id=order.restaurantId,
            total=order.total,
            delivery_location_id=order.deliveryLocationId,
            status=order.status.value if hasattr(order.status, "value") else order.status,
            drone_id=order.droneId,
        )
    )

    # Insert items
    if order.items:
        values = [
            {
                "order_id": order_id,
                "item_id": it.id,
                "name": it.name,
                "price": it.price,
                "quantity": it.quantity,
                "restaurant_id": it.restaurantId,
            }
            for it in order.items
        ]
        query = order_items.insert()
        await database.execute_many(query, values)

    full_order = await _fetch_order_with_items(order_id)

    # broadcast event
    await broadcast({
        "event": "order_created",
        "order": full_order,
    })

    return full_order


async def get_orders() -> List[Dict[str, Any]]:
    rows = await database.fetch_all(orders.select().order_by(orders.c.created_at.desc()))
    results: List[Dict[str, Any]] = []
    for row in rows:
        results.append(await _fetch_order_with_items(row["id"]))
    return results


async def get_order(order_id: str) -> Dict[str, Any]:
    return await _fetch_order_with_items(order_id)


async def update_order(order_id: str, payload: schemas.OrderUpdate):
    values = {}
    if payload.status is not None:
        values["status"] = payload.status.value if hasattr(payload.status, "value") else payload.status
    if payload.droneId is not None:
        values["drone_id"] = payload.droneId

    if values:
        await database.execute(orders.update().where(orders.c.id == order_id).values(**values))

    full_order = await _fetch_order_with_items(order_id)

    if full_order:
        await broadcast({
            "event": "order_updated",
            "order": full_order,
        })

    return full_order
