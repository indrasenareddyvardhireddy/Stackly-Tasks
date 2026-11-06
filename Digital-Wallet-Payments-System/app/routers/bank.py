from typing import Optional

from fastapi import APIRouter, BackgroundTasks, Depends, Header, HTTPException, Request
from sqlalchemy.orm import Session

from app.auth.dependencies import require_user_or_merchant
from app.database import get_db
from app.models import BankAccount, OTPPurpose, User, Withdrawal, WithdrawalStatus
from app.schemas.common import Page, paginated
from app.schemas.wallet import BankAccountCreate, WithdrawalRequest
from app.services.idempotency import run_idempotent
from app.services.otp import check_otp
from app.services.withdrawals import request_withdrawal
from app.utils.common import jsonable, mask_account

router = APIRouter(tags=["Bank Accounts & Withdrawals"])
IDEM = Header(None, alias="Idempotency-Key", description="Unique value (e.g. UUID) created by the client")
MAX_BANK_ACCOUNTS = 3


def bank_dict(b: BankAccount) -> dict:
    return jsonable({"id": b.id, "account_holder_name": b.account_holder_name,
                     "account_number": mask_account(b.account_number), "ifsc_code": b.ifsc_code,
                     "bank_name": b.bank_name, "is_primary": b.is_primary, "created_at": b.created_at})


def _active(db: Session, user: User):
    return db.query(BankAccount).filter(BankAccount.user_id == user.id, BankAccount.is_active.is_(True))


@router.post("/bank-accounts", status_code=201)
def add_bank_account(body: BankAccountCreate, user: User = Depends(require_user_or_merchant), db: Session = Depends(get_db)):
    existing = _active(db, user).all()
    if len(existing) >= MAX_BANK_ACCOUNTS:
        raise HTTPException(400, "You can link at most 3 bank accounts")
    if any(b.account_number == body.account_number and b.ifsc_code == body.ifsc_code for b in existing):
        raise HTTPException(409, "This bank account is already linked")
    check_otp(db, user, OTPPurpose.ADD_BANK_ACCOUNT, body.otp, consume=True)
    primary = body.is_primary or not existing
    if primary:
        for b in existing:
            b.is_primary = False
    acct = BankAccount(user_id=user.id, account_holder_name=body.account_holder_name, account_number=body.account_number,
                       ifsc_code=body.ifsc_code, bank_name=body.bank_name, is_primary=primary)
    db.add(acct)
    db.commit()
    return bank_dict(acct)


@router.get("/bank-accounts")
def list_bank_accounts(user: User = Depends(require_user_or_merchant), db: Session = Depends(get_db)):
    return [bank_dict(b) for b in _active(db, user).order_by(BankAccount.id).all()]


@router.delete("/bank-accounts/{bank_account_id}")
def delete_bank_account(bank_account_id: int, user: User = Depends(require_user_or_merchant), db: Session = Depends(get_db)):
    b = _active(db, user).filter(BankAccount.id == bank_account_id).first()
    if b is None:
        raise HTTPException(404, "Bank account not found")
    b.is_active = False  # soft delete: past withdrawals keep their reference
    was_primary, b.is_primary = b.is_primary, False
    if was_primary:
        nxt = _active(db, user).filter(BankAccount.id != b.id).order_by(BankAccount.id).first()
        if nxt:
            nxt.is_primary = True
    db.commit()
    return {"message": "Bank account removed"}


@router.post("/withdrawals", status_code=201)
def withdraw(body: WithdrawalRequest, request: Request, background_tasks: BackgroundTasks,
             idempotency_key: Optional[str] = IDEM, user: User = Depends(require_user_or_merchant),
             db: Session = Depends(get_db)):
    return run_idempotent(db, user, request, idempotency_key, body.model_dump(mode="json"),
                          lambda n: request_withdrawal(db, user, body, n), background_tasks)


@router.get("/withdrawals")
def list_withdrawals(status: Optional[WithdrawalStatus] = None, page: Page = Depends(),
                     user: User = Depends(require_user_or_merchant), db: Session = Depends(get_db)):
    q = db.query(Withdrawal).filter(Withdrawal.user_id == user.id)
    if status:
        q = q.filter(Withdrawal.status == status)
    total = q.count()
    rows = q.order_by(Withdrawal.id.desc()).offset(page.skip).limit(page.limit).all()
    items = [{"id": w.id, "transaction_ref": w.transaction.transaction_ref, "bank_account_id": w.bank_account_id,
              "bank_account": mask_account(w.bank_account.account_number), "amount": w.amount, "status": w.status,
              "processed_at": w.processed_at, "failure_reason": w.failure_reason, "created_at": w.created_at} for w in rows]
    return paginated(jsonable(items), total, page)
