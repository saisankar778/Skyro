import hmac
import hashlib
import os
from typing import Optional

import razorpay
from fastapi import APIRouter, HTTPException, Header
from pydantic import BaseModel

from auth import _verify_access_token

router = APIRouter(prefix="/api/payments/razorpay", tags=["payments"])


RAZORPAY_KEY_ID = os.getenv("RAZORPAY_KEY_ID")
RAZORPAY_KEY_SECRET = os.getenv("RAZORPAY_KEY_SECRET")


def _client() -> razorpay.Client:
    if not RAZORPAY_KEY_ID or not RAZORPAY_KEY_SECRET:
        raise HTTPException(status_code=500, detail="Razorpay keys not configured")
    return razorpay.Client(auth=(RAZORPAY_KEY_ID, RAZORPAY_KEY_SECRET))


class CreateOrderRequest(BaseModel):
    amount: int  # paise
    currency: str = "INR"
    receipt: Optional[str] = None


class CreateOrderResponse(BaseModel):
    keyId: str
    orderId: str
    amount: int
    currency: str


@router.post("/order", response_model=CreateOrderResponse)
def create_order(req: CreateOrderRequest, authorization: Optional[str] = Header(default=None)):
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing Bearer token")
    _verify_access_token(authorization.split(" ", 1)[1].strip())

    if req.amount <= 0:
        raise HTTPException(status_code=400, detail="amount must be > 0")

    client = _client()
    try:
        order = client.order.create(
            {
                "amount": req.amount,
                "currency": req.currency,
                "receipt": req.receipt,
                "payment_capture": 1,
            }
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to create Razorpay order: {e}")

    return CreateOrderResponse(
        keyId=RAZORPAY_KEY_ID,
        orderId=order["id"],
        amount=order["amount"],
        currency=order["currency"],
    )


class VerifyRequest(BaseModel):
    razorpay_order_id: str
    razorpay_payment_id: str
    razorpay_signature: str


class VerifyResponse(BaseModel):
    verified: bool


@router.post("/verify", response_model=VerifyResponse)
def verify(req: VerifyRequest, authorization: Optional[str] = Header(default=None)):
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing Bearer token")
    _verify_access_token(authorization.split(" ", 1)[1].strip())

    if not RAZORPAY_KEY_SECRET:
        raise HTTPException(status_code=500, detail="Razorpay keys not configured")

    payload = f"{req.razorpay_order_id}|{req.razorpay_payment_id}".encode("utf-8")
    expected = hmac.new(
        RAZORPAY_KEY_SECRET.encode("utf-8"),
        payload,
        hashlib.sha256,
    ).hexdigest()

    if not hmac.compare_digest(expected, req.razorpay_signature):
        raise HTTPException(status_code=400, detail="Invalid payment signature")

    return VerifyResponse(verified=True)
