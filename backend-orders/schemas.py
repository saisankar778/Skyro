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
