from enum import Enum
from typing import List, Optional
from pydantic import BaseModel, Field


class OrderStatus(str, Enum):
    PLACED = 'Placed'
    DECLINED = 'Declined'
    ACCEPTED = 'Accepted'
    COOKING = 'Cooking'
    READY_FOR_LAUNCH = 'Ready for Launch'
    EN_ROUTE = 'En Route'
    DELIVERED = 'Delivered'
    FAILED = 'Failed'

    # Uppercase variations to support mobile clients
    PREPARING_UPPER = 'PREPARING'
    ACCEPTED_UPPER = 'ACCEPTED'
    COOKING_UPPER = 'COOKING'
    READY_FOR_LAUNCH_UPPER = 'READY_FOR_LAUNCH'
    IN_FLIGHT_UPPER = 'IN_FLIGHT'
    ARRIVED_UPPER = 'ARRIVED'
    DELIVERED_UPPER = 'DELIVERED'
    DECLINED_UPPER = 'DECLINED'
    FAILED_UPPER = 'FAILED'
    PLACED_UPPER = 'PLACED'


class OrderItem(BaseModel):
    id: str
    name: str
    price: float
    quantity: int
    restaurantId: str


class OrderCreate(BaseModel):
    # Allow frontend to provide an id; backend generates if missing
    id: Optional[str] = None
    user: str
    restaurantId: str
    items: List[OrderItem]
    total: float
    deliveryLocationId: str
    status: OrderStatus = OrderStatus.PLACED
    droneId: Optional[str] = None


class OrderUpdate(BaseModel):
    status: Optional[OrderStatus] = None
    droneId: Optional[str] = None
    assigned_drone_id: Optional[str] = None


class AssignDronePayload(BaseModel):
    """Used by POST /api/orders/{id}/assign-drone from Fleet AI."""
    drone_id: str


class LocationOut(BaseModel):
    id: str
    name: str
    type: str
    latitude: float
    longitude: float
    is_active: bool = True


class RestaurantOut(BaseModel):
    id: str
    name: str
    tagline: Optional[str] = None
    rating: float = 0.0
    cuisine: Optional[str] = None
    delivery_time_min: int = 20
    price_for_two: int = 300
    offer: Optional[str] = None
    image_url: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    is_active: bool = True


class MenuItemOut(BaseModel):
    id: str
    restaurant_id: str
    name: str
    description: Optional[str] = None
    price: float
    category: Optional[str] = None
    image_url: Optional[str] = None
    is_available: bool = True
    is_veg: bool = False
    weight_grams: int = 300


class FoodCategoryOut(BaseModel):
    id: str
    name: str
    emoji: str = "🍽️"
    sort_order: int = 0


class HomeReservationCreate(BaseModel):
    zone: str
    drone_id: Optional[str] = None
    reserved: bool


class Order(BaseModel):
    id: str
    user: str
    restaurantId: str
    items: List[OrderItem]
    total: float
    deliveryLocationId: str
    status: OrderStatus
    createdAt: str
    droneId: Optional[str] = None
    assigned_drone_id: Optional[str] = None  # Fleet AI atomic lock field

    class Config:
        json_schema_extra = {
            "example": {
                "id": "ORD-1712345678901",
                "user": "Student-1",
                "restaurantId": "rest-1",
                "items": [
                    {"id": "item-1", "name": "Margherita Pizza", "price": 9.99, "quantity": 1, "restaurantId": "rest-1"}
                ],
                "total": 9.99,
                "deliveryLocationId": "loc-a",
                "status": "Placed",
                "createdAt": "2025-01-01T12:00:00Z",
                "droneId": None
            }
        }
