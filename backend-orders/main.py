from fastapi import FastAPI
from dotenv import load_dotenv
import os

load_dotenv()

from fastapi.middleware.cors import CORSMiddleware
from typing import List
import crud, schemas, database
from events import router as events_router
from auth import router as auth_router
from payments import router as payments_router

app = FastAPI(title="Drone Delivery Orders Service")

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

# ------------------- REST API -------------------
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

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
