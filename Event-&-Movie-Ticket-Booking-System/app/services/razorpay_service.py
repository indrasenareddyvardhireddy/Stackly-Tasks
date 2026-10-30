"""Thin Razorpay client using only the standard library (no extra package needed)."""
import base64
import json
import logging
import urllib.error
import urllib.request
from typing import Optional

from fastapi import HTTPException

from app.config import settings
from app.utils import razorpay_sig

logger = logging.getLogger(__name__)
ORDERS_URL = "https://api.razorpay.com/v1/orders"


def is_configured() -> bool:
    return bool(settings.RAZORPAY_KEY_ID and settings.RAZORPAY_KEY_SECRET)


def create_order(amount_paise: int, receipt: str, notes: Optional[dict] = None) -> dict:
    if not is_configured():
        raise HTTPException(status_code=503, detail="Razorpay is not configured (set RAZORPAY_KEY_ID / RAZORPAY_KEY_SECRET)")
    body = json.dumps({"amount": amount_paise, "currency": "INR", "receipt": receipt,
                       "payment_capture": 1, "notes": notes or {}}).encode()
    token = base64.b64encode(f"{settings.RAZORPAY_KEY_ID}:{settings.RAZORPAY_KEY_SECRET}".encode()).decode()
    request = urllib.request.Request(ORDERS_URL, data=body, method="POST", headers={
        "Content-Type": "application/json", "Authorization": f"Basic {token}"})
    try:
        with urllib.request.urlopen(request, timeout=15) as response:
            return json.loads(response.read())
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode(errors="replace")
        logger.error("Razorpay order creation failed: %s %s", exc.code, detail)
        raise HTTPException(status_code=502, detail=f"Razorpay rejected the order: {detail}")
    except Exception:
        logger.exception("Could not reach Razorpay")
        raise HTTPException(status_code=502, detail="Could not reach Razorpay, please try again")


def verify_payment_signature(order_id: str, payment_id: str, signature: str) -> bool:
    return razorpay_sig.verify_payment_signature(order_id, payment_id, signature, settings.RAZORPAY_KEY_SECRET)


def verify_webhook_signature(raw_body: bytes, signature: str) -> bool:
    return razorpay_sig.verify_webhook_signature(raw_body, signature, settings.RAZORPAY_WEBHOOK_SECRET)
