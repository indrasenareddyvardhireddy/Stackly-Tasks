from typing import Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy.orm import Session, joinedload

from app.auth.dependencies import require_admin
from app.database import get_db
from app.jobs.tasks import reconcile
from app.models import KYC, KYCLevel, KYCStatus, Transaction, TxnStatus, User, Wallet, WalletStatus
from app.routers.wallet import kyc_dict
from app.schemas.common import Page, paginated
from app.schemas.wallet import ReasonRequest
from app.services import fraud
from app.services.history import txn_dict
from app.services.ledger import lock_wallets
from app.utils.common import jsonable
from app.utils.email import Notifier

router = APIRouter(prefix="/admin", tags=["Admin"])


@router.get("/kyc")
def list_kyc(status: Optional[KYCStatus] = None, page: Page = Depends(), admin: User = Depends(require_admin),
             db: Session = Depends(get_db)):
    q = db.query(KYC)
    if status:
        q = q.filter(KYC.status == status)
    total = q.count()
    items = q.order_by(KYC.id.desc()).offset(page.skip).limit(page.limit).all()
    return paginated([kyc_dict(k) for k in items], total, page)


def _pending_kyc(db: Session, kyc_id: int) -> KYC:
    k = db.query(KYC).filter(KYC.id == kyc_id).with_for_update().first()
    if not k:
        raise HTTPException(404, "KYC record not found")
    if k.status != KYCStatus.PENDING:
        raise HTTPException(400, f"KYC is already {k.status.value}")
    return k


@router.put("/kyc/{kyc_id}/approve")
def approve_kyc(kyc_id: int, background_tasks: BackgroundTasks, admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    k = _pending_kyc(db, kyc_id)
    wallet = db.query(Wallet).filter(Wallet.owner_id == k.user_id).first()
    lock_wallets(db, [wallet.id])[wallet.id].kyc_level = KYCLevel.FULL
    k.status, k.reviewed_by, k.rejection_reason = KYCStatus.APPROVED, admin.id, None
    n = Notifier()
    n.add(k.user.email, "KYC approved", "Your KYC is approved. Your wallet is upgraded to Full KYC with higher limits.")
    db.commit()
    n.flush(background_tasks)
    return kyc_dict(k)


@router.put("/kyc/{kyc_id}/reject")
def reject_kyc(kyc_id: int, body: ReasonRequest, background_tasks: BackgroundTasks, admin: User = Depends(require_admin),
               db: Session = Depends(get_db)):
    k = _pending_kyc(db, kyc_id)
    k.status, k.reviewed_by, k.rejection_reason = KYCStatus.REJECTED, admin.id, body.reason
    n = Notifier()
    n.add(k.user.email, "KYC rejected", f"Your KYC was rejected. Reason: {body.reason}. You can resubmit.")
    db.commit()
    n.flush(background_tasks)
    return kyc_dict(k)


def _set_wallet_status(db, wallet_id: int, status: WalletStatus, reason: Optional[str]):
    if not db.query(Wallet.id).filter(Wallet.id == wallet_id).first():
        raise HTTPException(404, "Wallet not found")
    w = lock_wallets(db, [wallet_id])[wallet_id]
    if w.status == status:
        raise HTTPException(409, f"Wallet is already {status.value}")
    w.status = status
    w.freeze_reason = reason if status == WalletStatus.FROZEN else None
    db.commit()
    return {"wallet_id": w.id, "wallet_number": w.wallet_number, "status": w.status.value, "freeze_reason": w.freeze_reason}


@router.put("/wallets/{wallet_id}/freeze")
def freeze_wallet(wallet_id: int, body: ReasonRequest, admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    return _set_wallet_status(db, wallet_id, WalletStatus.FROZEN, body.reason)


@router.put("/wallets/{wallet_id}/unfreeze")
def unfreeze_wallet(wallet_id: int, admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    return _set_wallet_status(db, wallet_id, WalletStatus.ACTIVE, None)


# ------------------------------------------------------------------ fraud review
@router.get("/flagged-transactions")
def flagged(status: Optional[TxnStatus] = TxnStatus.ON_HOLD, page: Page = Depends(), admin: User = Depends(require_admin),
            db: Session = Depends(get_db)):
    q = db.query(Transaction).filter(Transaction.is_flagged.is_(True))
    if status:
        q = q.filter(Transaction.status == status)
    total = q.count()
    items = q.order_by(Transaction.id.desc()).offset(page.skip).limit(page.limit).all()
    return paginated([jsonable(txn_dict(t, None)) for t in items], total, page)


def _decide(db, admin, ref, body, approve, background_tasks):
    n = Notifier()
    result = fraud.decide(db, admin, ref, approve, body.reason, n)
    db.commit()
    n.flush(background_tasks)
    return jsonable(result)


@router.put("/transactions/{transaction_ref}/approve")
def approve_txn(transaction_ref: str, body: ReasonRequest, background_tasks: BackgroundTasks,
                admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    return _decide(db, admin, transaction_ref, body, True, background_tasks)


@router.put("/transactions/{transaction_ref}/reject")
def reject_txn(transaction_ref: str, body: ReasonRequest, background_tasks: BackgroundTasks,
               admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    return _decide(db, admin, transaction_ref, body, False, background_tasks)


@router.post("/reconciliation/run")
def run_reconciliation(admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    """Runs the same check as the daily reconciliation job and returns the result."""
    return jsonable(reconcile(db))
