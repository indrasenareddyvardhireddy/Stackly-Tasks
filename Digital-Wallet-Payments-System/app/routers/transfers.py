from typing import Optional

from fastapi import APIRouter, BackgroundTasks, Depends, Header, HTTPException, Request
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user, require_user
from app.database import get_db
from app.models import Role, Transaction, TxnType, User
from app.schemas.wallet import TransferRequest
from app.services.history import balances_after, can_view, txn_dict
from app.services.idempotency import run_idempotent
from app.services.money import execute_transfer, find_receiver
from app.utils.common import jsonable

router = APIRouter(tags=["Transfers"])
IDEM = Header(None, alias="Idempotency-Key", description="Unique value (e.g. UUID) created by the client")


@router.post("/transfers", status_code=201)
def send_money(body: TransferRequest, request: Request, background_tasks: BackgroundTasks,
               idempotency_key: Optional[str] = IDEM, user: User = Depends(require_user), db: Session = Depends(get_db)):
    def handler(notifier):
        receiver = find_receiver(db, body.receiver_phone)
        resp, status, _ = execute_transfer(db, user, receiver, body.amount, body.note, body.pin, body.otp, notifier)
        return resp, status
    return run_idempotent(db, user, request, idempotency_key, body.model_dump(mode="json"), handler, background_tasks)


@router.get("/transfers/{transaction_ref}")
def get_transfer(transaction_ref: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    t = db.query(Transaction).filter(Transaction.transaction_ref == transaction_ref,
                                     Transaction.type == TxnType.P2P_TRANSFER).first()
    if t is None or (user.role != Role.ADMIN and not can_view(t, user.wallet)):
        raise HTTPException(404, "Transfer not found")
    if user.role == Role.ADMIN:
        return jsonable(txn_dict(t, None))
    bal = balances_after(db, [t.id], user.wallet.account.id).get(t.id)
    return jsonable(txn_dict(t, user.wallet.id, bal))
