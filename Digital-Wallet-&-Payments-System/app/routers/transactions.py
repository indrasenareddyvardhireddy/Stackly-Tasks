from datetime import date
from decimal import Decimal
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse
from sqlalchemy import asc, desc, or_
from sqlalchemy.orm import Session, joinedload

from app.auth.dependencies import get_current_user, require_user_or_merchant
from app.database import get_db
from app.models import LedgerEntry, Role, Transaction, TxnStatus, TxnType, User, Wallet
from app.schemas.common import Page, paginated
from app.services.history import balances_after, can_view, txn_dict
from app.services.statements import build_statement, write_csv, write_pdf
from app.utils.common import ist_date_start_utc, jsonable
from datetime import timedelta

router = APIRouter(tags=["Transactions & Statements"])


@router.get("/transactions")
def list_transactions(type: Optional[TxnType] = None, status: Optional[TxnStatus] = None,
                      min_amount: Optional[Decimal] = Query(None, ge=0), max_amount: Optional[Decimal] = Query(None, ge=0),
                      from_date: Optional[date] = None, to_date: Optional[date] = None,
                      sort_by: str = Query("date", pattern="^(date|amount)$"), order: str = Query("desc", pattern="^(asc|desc)$"),
                      page: Page = Depends(), user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    q = db.query(Transaction).options(
        joinedload(Transaction.sender_wallet).joinedload(Wallet.owner).joinedload(User.merchant),
        joinedload(Transaction.receiver_wallet).joinedload(Wallet.owner).joinedload(User.merchant))
    wallet = user.wallet
    if user.role != Role.ADMIN:
        q = q.filter(or_(Transaction.sender_wallet_id == wallet.id, Transaction.receiver_wallet_id == wallet.id))
    if type:
        q = q.filter(Transaction.type == type)
    if status:
        q = q.filter(Transaction.status == status)
    if min_amount is not None:
        q = q.filter(Transaction.amount >= min_amount)
    if max_amount is not None:
        q = q.filter(Transaction.amount <= max_amount)
    if from_date:
        q = q.filter(Transaction.created_at >= ist_date_start_utc(from_date))
    if to_date:
        q = q.filter(Transaction.created_at < ist_date_start_utc(to_date + timedelta(days=1)))
    total = q.with_entities(Transaction.id).count()
    col = Transaction.created_at if sort_by == "date" else Transaction.amount
    q = q.order_by((asc if order == "asc" else desc)(col), desc(Transaction.id))
    rows = q.offset(page.skip).limit(page.limit).all()
    bals = balances_after(db, [t.id for t in rows], wallet.account.id) if wallet else {}
    items = [txn_dict(t, wallet.id if user.role != Role.ADMIN else None, bals.get(t.id)) for t in rows]
    return paginated(jsonable(items), total, page)


@router.get("/transactions/{transaction_ref}")
def get_transaction(transaction_ref: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    t = db.query(Transaction).filter(Transaction.transaction_ref == transaction_ref).first()
    if t is None or (user.role != Role.ADMIN and not can_view(t, user.wallet)):
        raise HTTPException(404, "Transaction not found")
    if user.role == Role.ADMIN:
        d = txn_dict(t, None)
        d["ledger_entries"] = [{"account": e.account.name, "account_type": e.account.account_type, "entry_type": e.entry_type,
                                "amount": e.amount, "balance_after": e.balance_after}
                               for e in sorted(t.entries, key=lambda e: e.id)]
        return jsonable(d)
    bal = balances_after(db, [t.id], user.wallet.account.id).get(t.id)
    return jsonable(txn_dict(t, user.wallet.id, bal))


@router.get("/statements")
def statement(month: str = Query(..., description="YYYY-MM, e.g. 2026-10"),
              format: str = Query("pdf", pattern="^(pdf|csv)$"),
              user: User = Depends(require_user_or_merchant), db: Session = Depends(get_db)):
    data = build_statement(db, user, user.wallet, month)
    if format == "csv":
        path = write_csv(data, user.id)
        return FileResponse(path, media_type="text/csv", filename=path.split("/")[-1])
    path = write_pdf(data, user.id)
    return FileResponse(path, media_type="application/pdf", filename=path.split("/")[-1])
