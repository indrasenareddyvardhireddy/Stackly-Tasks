from datetime import timedelta

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.auth.security import verify_secret
from app.models import User
from app.utils.common import utcnow

MAX_PIN_ATTEMPTS = 3
LOCK_MINUTES = 30


def verify_pin(db: Session, user: User, pin: str) -> None:
    """Checks the transaction PIN. Failed attempts are committed immediately (no money has moved yet)."""
    u = db.query(User).filter(User.id == user.id).with_for_update().populate_existing().one()
    now = utcnow()
    if u.pin_hash is None:
        raise HTTPException(status_code=400, detail="Set a transaction PIN first (POST /wallet/pin)")
    if u.pin_locked_until and u.pin_locked_until > now:
        mins = int((u.pin_locked_until - now).total_seconds() // 60) + 1
        raise HTTPException(status_code=423, detail=f"Payments are locked due to wrong PIN attempts. Try again in {mins} minute(s)")
    if not verify_secret(pin, u.pin_hash):
        u.pin_failed_attempts = (u.pin_failed_attempts or 0) + 1
        if u.pin_failed_attempts >= MAX_PIN_ATTEMPTS:
            u.pin_locked_until = now + timedelta(minutes=LOCK_MINUTES)
            u.pin_failed_attempts = 0
            db.commit()
            raise HTTPException(status_code=423, detail="Too many wrong PIN attempts. Payments are locked for 30 minutes")
        left = MAX_PIN_ATTEMPTS - u.pin_failed_attempts
        db.commit()
        raise HTTPException(status_code=400, detail=f"Incorrect PIN. {left} attempt(s) remaining")
    u.pin_failed_attempts = 0
    u.pin_locked_until = None
    db.flush()
