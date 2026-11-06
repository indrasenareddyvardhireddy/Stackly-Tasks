import secrets
from datetime import timedelta
from typing import Optional

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.auth.security import hash_secret, verify_secret
from app.models import OTP, OTPPurpose, User
from app.utils.common import utcnow
from app.utils.email import Notifier

OTP_TTL_MIN = 5
OTP_MAX_ATTEMPTS = 3
OTP_COOLDOWN_SEC = 60


def create_otp(db: Session, user: User, purpose: OTPPurpose, notifier: Notifier) -> str:
    now = utcnow()
    last = db.query(OTP).filter(OTP.user_id == user.id).order_by(OTP.id.desc()).first()
    if last and (now - last.created_at).total_seconds() < OTP_COOLDOWN_SEC:
        wait = OTP_COOLDOWN_SEC - int((now - last.created_at).total_seconds())
        raise HTTPException(status_code=429, detail=f"Please wait {wait} second(s) before requesting a new OTP")
    # a new OTP replaces any older unused one for the same purpose
    db.query(OTP).filter(OTP.user_id == user.id, OTP.purpose == purpose, OTP.is_used.is_(False)).update(
        {"is_used": True}, synchronize_session=False)
    code = f"{secrets.randbelow(1_000_000):06d}"
    db.add(OTP(user_id=user.id, purpose=purpose, otp_hash=hash_secret(code),
               expires_at=now + timedelta(minutes=OTP_TTL_MIN)))
    db.flush()
    notifier.add(user.email, f"Your OTP for {purpose.value}",
                 f"Your one-time password is {code}. It is valid for {OTP_TTL_MIN} minutes. Do not share it with anyone.")
    return code


def check_otp(db: Session, user: User, purpose: OTPPurpose, code: Optional[str], consume: bool) -> None:
    """Validates the OTP for exactly this purpose. Wrong attempts are committed immediately."""
    if not code:
        raise HTTPException(status_code=400, detail=f"OTP is required for: {purpose.value}")
    rec = (db.query(OTP).filter(OTP.user_id == user.id, OTP.purpose == purpose, OTP.is_used.is_(False))
           .order_by(OTP.id.desc()).with_for_update().populate_existing().first())
    if rec is None:
        raise HTTPException(status_code=400, detail=f"No active OTP for '{purpose.value}'. Request a new OTP")
    if rec.expires_at < utcnow():
        raise HTTPException(status_code=400, detail="OTP has expired. Request a new OTP")
    if rec.attempts >= OTP_MAX_ATTEMPTS:
        raise HTTPException(status_code=400, detail="Too many wrong attempts for this OTP. Request a new OTP")
    if not verify_secret(code, rec.otp_hash):
        rec.attempts += 1
        left = OTP_MAX_ATTEMPTS - rec.attempts
        db.commit()
        raise HTTPException(status_code=400, detail=f"Incorrect OTP. {left} attempt(s) remaining")
    if consume:
        rec.is_used = True
        db.flush()
