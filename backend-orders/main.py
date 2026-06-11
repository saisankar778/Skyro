from fastapi import FastAPI, Query
from dotenv import load_dotenv
import os

load_dotenv()

from fastapi.middleware.cors import CORSMiddleware
from typing import List, Optional
import crud, schemas, database
from schemas import AssignDronePayload
from schemas import FoodCategoryOut
from events import router as events_router
from auth import router as auth_router
from payments import router as payments_router

app = FastAPI(title="Skyro Drone Delivery — Orders Service")

# allow your three frontends
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # TODO: restrict in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# include websocket router
app.include_router(events_router)
app.include_router(auth_router)
app.include_router(payments_router)

# startup/shutdown
@app.on_event("startup")
async def startup():
    await database.database.connect()

@app.on_event("shutdown")
async def shutdown():
    await database.database.disconnect()

# ------------------- ORDERS API -------------------
@app.post("/api/orders", response_model=schemas.Order)
async def create_order(order: schemas.OrderCreate):
    return await crud.create_order(order)

@app.get("/api/orders", response_model=List[schemas.Order])
async def list_orders():
    return await crud.get_orders()

@app.get("/api/orders/{order_id}", response_model=schemas.Order)
async def get_order(order_id: str):
    return await crud.get_order(order_id)

@app.patch("/api/orders/{order_id}", response_model=schemas.Order)
async def update_order(order_id: str, payload: schemas.OrderUpdate):
    return await crud.update_order(order_id, payload)


# ------------------- LOCATIONS API -------------------
@app.get("/api/locations", response_model=List[schemas.LocationOut])
async def list_locations(type: Optional[str] = Query(None)):
    """Fetch locations — used by Fleet AI and frontend delivery dropdowns."""
    return await crud.get_locations(type)


@app.post("/api/locations/home-reservations")
async def sync_home_reservation(payload: schemas.HomeReservationCreate):
    """Fleet AI calls this to persist in-memory home locks to PostgreSQL."""
    result = await crud.upsert_home_reservation(
        zone=payload.zone,
        drone_id=payload.drone_id,
        reserved=payload.reserved
    )
    if not result:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Location not found")
    return {"status": "ok"}


# ------------------- RESTAURANTS API -------------------
@app.get("/api/restaurants", response_model=List[schemas.RestaurantOut])
async def list_restaurants():
    """
    Return all active restaurants with GPS, rating, offer and image.
    Frontend uses this to build the restaurant catalogue — no hardcoded data needed.
    """
    return await crud.get_restaurants()


# ------------------- MENU ITEMS API -------------------
@app.get("/api/menu-items", response_model=List[schemas.MenuItemOut])
async def list_menu_items(restaurant_id: Optional[str] = Query(None)):
    """
    Return menu items, optionally filtered by restaurant_id.
    Frontend calls this when user selects a restaurant.
    """
    return await crud.get_menu_items(restaurant_id)


# ------------------- FOOD CATEGORIES API -------------------
@app.get("/api/categories", response_model=List[FoodCategoryOut])
async def list_categories():
    """
    Return all food categories for the home screen filter pills.
    Android app fetches these and replaces hardcoded category list.
    """
    return await crud.get_categories()


# ------------------- FLEET AI ASSIGNMENT -------------------
@app.post("/api/orders/{order_id}/assign-drone", response_model=schemas.Order)
async def assign_drone_to_order(order_id: str, payload: AssignDronePayload):
    """
    Fleet AI calls this to atomically lock an order to a drone.

    Uses SQL UPDATE ... WHERE assigned_drone_id IS NULL to guarantee that
    only ONE drone can ever be assigned to a given order, even under
    concurrent requests (prevents double-dispatch).

    Returns 409 if the order is already assigned to a different drone.
    """
    result = await crud.assign_drone_to_order(order_id, payload.drone_id)
    if result is None:
        from fastapi import HTTPException
        existing = await crud.get_order(order_id)
        holder = (existing or {}).get("assigned_drone_id", "another drone")
        raise HTTPException(
            status_code=409,
            detail=(
                f"Order '{order_id}' is already assigned to drone '{holder}'. "
                f"Atomic lock rejected assignment to '{payload.drone_id}'."
            ),
        )
    return result

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
