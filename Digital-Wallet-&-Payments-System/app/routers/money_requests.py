from datetime import timedelta
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, Depends, Header, HTTPException, Request
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.auth.dependencies import require_user
from app.database import get_db
from app.models import MoneyRequest, RequestStatus, User
from app.schemas.common import Page, paginated
from app.schemas.wallet import MoneyRequestCreate, MoneyRequestPay
from app.services.idempotency import run_idempotent
from app.services.money import execute_transfer, find_receiver, own_wallet
from app.utils.common import inr, jsonable, mask_phone, q2, utcnow
from app.utils.email import Notifier

router = APIRouter(prefix="/money-requests", tags=["Money Requests"])
IDEM = Header(None, alias="Idempotency-Key", description="Unique value (e.g. UUID) created by the client")
MAX_PENDING_PER_PAYER = 5
EXPIRY = timedelta(hours=48)


def req_dict(r: MoneyRequest, me: int) -> dict:
    other = r.payer if r.requester_id == me else r.requester
    return jsonable({"id": r.id, "direction": "sent" if r.requester_id == me else "received",
                     "requester": {"name": r.requester.full_name, "phone": mask_phone(r.requester.phone)},
                     "payer": {"name": r.payer.full_name, "phone": mask_phone(r.payer.phone)},
                     "amount": r.amount, "note": r.note, "status": r.status, "expires_at": r.expires_at,
                     "created_at": r.created_at})


@router.post("", status_code=201)
def create_request(body: MoneyRequestCreate, background_tasks: BackgroundTasks, user: User = Depends(require_user),
                   db: Session = Depends(get_db)):
    payer = find_receiver(db, body.payer_phone)
    if payer.id == user.id:
        raise HTTPException(400, "You cannot request money from yourself")
    now = utcnow()
    pending = (db.query(MoneyRequest).filter(MoneyRequest.requester_id == user.id, MoneyRequest.payer_id == payer.id,
                                             MoneyRequest.status == RequestStatus.PENDING, MoneyRequest.expires_at > now).count())
    if pending >= MAX_PENDING_PER_PAYER:
        raise HTTPException(409, "You already have 5 pending requests to this person")
    r = MoneyRequest(requester_id=user.id, payer_id=payer.id, amount=q2(body.amount), note=body.note,
                     status=RequestStatus.PENDING, expires_at=now + EXPIRY)
    db.add(r)
    db.commit()
    n = Notifier()
    n.add(payer.email, "Money request received", f"{user.full_name} requested {inr(r.amount)} from you. Note: {body.note or '-'}")
    n.flush(background_tasks)
    return req_dict(r, user.id)


@router.get("")
def list_requests(direction: Optional[str] = None, status: Optional[RequestStatus] = None, page: Page = Depends(),
                  user: User = Depends(require_user), db: Session = Depends(get_db)):
    db.query(MoneyRequest).filter(MoneyRequest.status == RequestStatus.PENDING, MoneyRequest.expires_at <= utcnow(),
                                  or_(MoneyRequest.requester_id == user.id, MoneyRequest.payer_id == user.id)
                                  ).update({"status": RequestStatus.EXPIRED}, synchronize_session=False)
    db.commit()
    q = db.query(MoneyRequest)
    if direction == "sent":
        q = q.filter(MoneyRequest.requester_id == user.id)
    elif direction == "received":
        q = q.filter(MoneyRequest.payer_id == user.id)
    else:
        q = q.filter(or_(MoneyRequest.requester_id == user.id, MoneyRequest.payer_id == user.id))
    if status:
        q = q.filter(MoneyRequest.status == status)
    total = q.count()
    rows = q.order_by(MoneyRequest.id.desc()).offset(page.skip).limit(page.limit).all()
    return paginated([req_dict(r, user.id) for r in rows], total, page)


def _locked_pending(db: Session, request_id: int) -> MoneyRequest:
    r = db.query(MoneyRequest).filter(MoneyRequest.id == request_id).with_for_update().populate_existing().first()
    if r is None:
        raise HTTPException(404, "Money request not found")
    return r


def _ensure_open(r: MoneyRequest):
    if r.status == RequestStatus.PENDING and r.expires_at <= utcnow():
        r.status = RequestStatus.EXPIRED
    if r.status != RequestStatus.PENDING:
        raise HTTPException(400, f"Request is {r.status.value}")


@router.put("/{request_id}/pay")
def pay_request(request_id: int, body: MoneyRequestPay, request: Request, background_tasks: BackgroundTasks,
                idempotency_key: Optional[str] = IDEM, user: User = Depends(require_user), db: Session = Depends(get_db)):
    def handler(notifier):
        r = _locked_pending(db, request_id)
        if r.payer_id != user.id:
            raise HTTPException(403, "Only the payer can pay this request")
        _ensure_open(r)
        resp, status, txn = execute_transfer(db, user, r.requester, r.amount, r.note, body.pin, body.otp, notifier,
                                             description_prefix="Money request payment")
        r.status = RequestStatus.PAID
        r.paid_transaction_id = txn.id
        resp["request_id"] = r.id
        return resp, 200
    return run_idempotent(db, user, request, idempotency_key, {"request_id": request_id, **body.model_dump(mode="json")},
                          handler, background_tasks)


@router.put("/{request_id}/decline")
def decline(request_id: int, user: User = Depends(require_user), db: Session = Depends(get_db)):
    r = _locked_pending(db, request_id)
    if r.payer_id != user.id:
        raise HTTPException(403, "Only the payer can decline this request")
    _ensure_open(r)
    r.status = RequestStatus.DECLINED
    db.commit()
    return req_dict(r, user.id)


@router.put("/{request_id}/cancel")
def cancel(request_id: int, user: User = Depends(require_user), db: Session = Depends(get_db)):
    r = _locked_pending(db, request_id)
    if r.requester_id != user.id:
        raise HTTPException(403, "Only the requester can cancel this request")
    _ensure_open(r)
    r.status = RequestStatus.CANCELLED
    db.commit()
    return req_dict(r, user.id)
