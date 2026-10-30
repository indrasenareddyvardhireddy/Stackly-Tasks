import json
import logging
from typing import Optional

from fastapi import APIRouter, Header, HTTPException, Request
from starlette.concurrency import run_in_threadpool

from app.config import settings
from app.database import SessionLocal
from app.redis_client import redis_client as r
from app.services import payment_service, razorpay_service

logger = logging.getLogger(__name__)
router = APIRouter(tags=["Webhooks"])


def _process(event: dict) -> str:
    db = SessionLocal()
    try:
        return payment_service.handle_razorpay_event(db, event)
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


@router.post("/webhooks/razorpay")
async def razorpay_webhook(request: Request,
                           x_razorpay_signature: Optional[str] = Header(default=None),
                           x_razorpay_event_id: Optional[str] = Header(default=None)):
    """Razorpay webhook (payment.captured, payment.failed). The raw body is verified with X-Razorpay-Signature."""
    if not settings.RAZORPAY_WEBHOOK_SECRET:
        raise HTTPException(status_code=503, detail="RAZORPAY_WEBHOOK_SECRET is not configured")
    raw_body = await request.body()
    if not x_razorpay_signature or not razorpay_service.verify_webhook_signature(raw_body, x_razorpay_signature):
        raise HTTPException(status_code=400, detail="Invalid webhook signature")
    try:
        event = json.loads(raw_body)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid JSON")

    # Razorpay retries deliveries: ignore an event id we already handled (payment ids are also de-duplicated in the DB)
    dedupe_key = f"rzp:event:{x_razorpay_event_id}" if x_razorpay_event_id else None
    if dedupe_key and r.exists(dedupe_key):
        return {"status": "duplicate event ignored"}
    result = await run_in_threadpool(_process, event)   # an exception here -> 500 -> Razorpay retries
    if dedupe_key:
        r.set(dedupe_key, "1", ex=86400)
    return {"status": result}
