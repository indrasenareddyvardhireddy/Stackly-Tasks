from typing import Optional

from fastapi import APIRouter, BackgroundTasks, Depends, Header, HTTPException, Request
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user, require_admin, require_user, require_user_or_merchant
from app.auth.security import hash_secret
from app.config import settings
from app.database import get_db
from app.models import KYC, KYCLevel, KYCStatus, OTPPurpose, Role, User, Wallet, WalletStatus
from app.schemas.wallet import (AddMoneyRequest, ChangePinRequest, KYCRequest, OTPSendRequest, OTPVerifyRequest,
                                ReasonRequest, ResetPinRequest, SetPinRequest)
from app.services import money
from app.services.idempotency import run_idempotent
from app.services.ledger import lock_wallets
from app.services.limits import LIMITS, limits_for
from app.services.otp import check_otp, create_otp
from app.services.pin import verify_pin
from app.utils.common import jsonable, utcnow
from app.utils.email import Notifier

router = APIRouter()
IDEM = Header(None, alias="Idempotency-Key", description="Unique value (e.g. UUID) created by the client")


def wallet_dict(w: Wallet, user: User) -> dict:
    lim = limits_for(w, user.role == Role.MERCHANT)
    return jsonable({"owner_id": w.owner_id, "wallet_number": w.wallet_number, "balance": w.balance,
                     "kyc_level": w.kyc_level, "status": w.status, "freeze_reason": w.freeze_reason,
                     "pin_set": user.pin_hash is not None,
                     "limits": {"max_balance": LIMITS[w.kyc_level]["balance"], "daily_send": lim["daily"],
                                "monthly_send": lim["monthly"], "bank_withdrawal_allowed": w.kyc_level == KYCLevel.FULL or user.role == Role.MERCHANT}})


@router.get("/wallet", tags=["Wallet"])
def get_wallet(user: User = Depends(require_user_or_merchant)):
    return wallet_dict(money.own_wallet(user), user)


@router.post("/wallet/add-money", tags=["Wallet"])
def add_money(body: AddMoneyRequest, request: Request, background_tasks: BackgroundTasks,
              idempotency_key: Optional[str] = IDEM, user: User = Depends(require_user), db: Session = Depends(get_db)):
    return run_idempotent(db, user, request, idempotency_key, body.model_dump(mode="json"),
                          lambda n: money.add_money(db, user, body, n), background_tasks)


# ------------------------------------------------------------------ PIN
@router.post("/wallet/pin", status_code=201, tags=["Wallet"])
def set_pin(body: SetPinRequest, user: User = Depends(require_user_or_merchant), db: Session = Depends(get_db)):
    if user.pin_hash is not None:
        raise HTTPException(409, "PIN is already set. Use PUT /wallet/pin/change")
    user.pin_hash = hash_secret(body.pin)
    db.commit()
    return {"message": "Transaction PIN set successfully"}


@router.put("/wallet/pin/change", tags=["Wallet"])
def change_pin(body: ChangePinRequest, user: User = Depends(require_user_or_merchant), db: Session = Depends(get_db)):
    verify_pin(db, user, body.old_pin)
    if body.old_pin == body.new_pin:
        raise HTTPException(400, "New PIN must be different from the old PIN")
    user.pin_hash = hash_secret(body.new_pin)
    db.commit()
    return {"message": "PIN changed successfully"}


@router.post("/wallet/pin/reset", tags=["Wallet"])
def reset_pin(body: ResetPinRequest, user: User = Depends(require_user_or_merchant), db: Session = Depends(get_db)):
    check_otp(db, user, OTPPurpose.PIN_RESET, body.otp, consume=True)
    user.pin_hash = hash_secret(body.new_pin)
    user.pin_failed_attempts = 0
    user.pin_locked_until = None
    db.commit()
    return {"message": "PIN reset successfully"}


# ------------------------------------------------------------------ OTP
@router.post("/otp/send", tags=["OTP"])
def send_otp(body: OTPSendRequest, background_tasks: BackgroundTasks, user: User = Depends(require_user_or_merchant),
             db: Session = Depends(get_db)):
    notifier = Notifier()
    code = create_otp(db, user, body.purpose, notifier)
    db.commit()
    notifier.flush(background_tasks)
    resp = {"message": "OTP sent to your registered email", "purpose": body.purpose.value, "expires_in_seconds": 300}
    if settings.DEBUG_RETURN_OTP:  # dev convenience only
        resp["otp"] = code
    return resp


@router.post("/otp/verify", tags=["OTP"])
def verify_otp(body: OTPVerifyRequest, user: User = Depends(require_user_or_merchant), db: Session = Depends(get_db)):
    """Checks the OTP without using it up (it is consumed by the action it was issued for)."""
    check_otp(db, user, body.purpose, body.otp, consume=False)
    return {"verified": True, "purpose": body.purpose.value}


# ------------------------------------------------------------------ KYC
def kyc_dict(k: KYC) -> dict:
    return jsonable({"id": k.id, "user_id": k.user_id, "pan_number": k.pan_number, "aadhaar_last4": k.aadhaar_last4,
                     "full_name": k.full_name, "date_of_birth": k.date_of_birth, "status": k.status,
                     "rejection_reason": k.rejection_reason, "submitted_at": k.updated_at})


@router.post("/kyc", status_code=201, tags=["KYC"])
def submit_kyc(body: KYCRequest, user: User = Depends(require_user_or_merchant), db: Session = Depends(get_db)):
    existing = db.query(KYC).filter(KYC.user_id == user.id).first()
    if existing and existing.status in (KYCStatus.PENDING, KYCStatus.APPROVED):
        raise HTTPException(409, f"KYC is already {existing.status.value}")
    pan_owner = db.query(KYC).filter(KYC.pan_number == body.pan_number).first()
    if pan_owner and pan_owner.user_id != user.id:
        raise HTTPException(409, "This PAN is already registered with another account")
    if existing:  # resubmission after rejection
        existing.pan_number, existing.aadhaar_last4 = body.pan_number, body.aadhaar_last4
        existing.full_name, existing.date_of_birth = body.full_name, body.date_of_birth
        existing.status, existing.rejection_reason = KYCStatus.PENDING, None
        kyc = existing
    else:
        kyc = KYC(user_id=user.id, pan_number=body.pan_number, aadhaar_last4=body.aadhaar_last4,
                  full_name=body.full_name, date_of_birth=body.date_of_birth, status=KYCStatus.PENDING)
        db.add(kyc)
    db.commit()
    return kyc_dict(kyc)


@router.get("/kyc", tags=["KYC"])
def get_kyc(user: User = Depends(require_user_or_merchant), db: Session = Depends(get_db)):
    k = db.query(KYC).filter(KYC.user_id == user.id).first()
    if not k:
        raise HTTPException(404, "No KYC submitted yet")
    return kyc_dict(k)