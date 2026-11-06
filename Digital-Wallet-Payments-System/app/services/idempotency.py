"""Idempotency-Key handling shared by every money API."""
import hashlib
import json
from datetime import timedelta
from typing import Callable, Optional, Tuple

from fastapi import BackgroundTasks, HTTPException, Request
from fastapi.responses import JSONResponse
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import IdempotencyKey, IdemStatus, User
from app.utils.common import jsonable, utcnow
from app.utils.email import Notifier

KEY_TTL = timedelta(hours=24)


def require_key(value: Optional[str]) -> str:
    if not value or not value.strip():
        raise HTTPException(status_code=400, detail="Idempotency-Key header is required for this endpoint")
    if len(value) > 128:
        raise HTTPException(status_code=400, detail="Idempotency-Key must be at most 128 characters")
    return value.strip()


def _hash(endpoint: str, body: dict) -> str:
    canon = json.dumps({"endpoint": endpoint, "body": body}, sort_keys=True, default=str)
    return hashlib.sha256(canon.encode()).hexdigest()


def run_idempotent(db: Session, user: User, request: Request, key: Optional[str], body: dict,
                   handler: Callable[[Notifier], Tuple[dict, int]], background_tasks: BackgroundTasks):
    """handler(notifier) does the whole money movement WITHOUT committing and returns (response_dict, status).
    The key row is saved/updated in the same DB transaction as the money movement."""
    key = require_key(key)
    endpoint = f"{request.method} {request.url.path}"
    req_hash = _hash(endpoint, body)
    user_id = user.id

    existing = db.query(IdempotencyKey).filter(IdempotencyKey.user_id == user_id, IdempotencyKey.key == key).first()
    if existing and existing.created_at < utcnow() - KEY_TTL:  # keys are valid for 24 hours
        db.delete(existing)
        db.commit()
        existing = None

    rec = existing
    if rec is None:
        rec = IdempotencyKey(user_id=user_id, key=key, endpoint=endpoint, request_hash=req_hash,
                             status=IdemStatus.PROCESSING)
        db.add(rec)
        try:
            db.commit()  # reserve the key; the unique (user_id, key) index makes this race-safe
        except IntegrityError:
            db.rollback()
            rec = db.query(IdempotencyKey).filter(IdempotencyKey.user_id == user_id, IdempotencyKey.key == key).first()
            if rec is None:
                raise HTTPException(status_code=409, detail="A request with this Idempotency-Key is being processed")
        else:
            return _execute(db, rec.id, handler, background_tasks)

    # key already known
    if rec.request_hash != req_hash:
        raise HTTPException(status_code=422, detail="Idempotency-Key was already used with a different request")
    if rec.status == IdemStatus.PROCESSING:
        raise HTTPException(status_code=409, detail="A request with this Idempotency-Key is still being processed")
    return JSONResponse(content=rec.response_body, status_code=rec.response_status,
                        headers={"Idempotent-Replayed": "true"})


def _execute(db: Session, rec_id: int, handler, background_tasks: BackgroundTasks):
    notifier = Notifier()
    try:
        response, status = handler(notifier)
        response = jsonable(response)
        rec = db.query(IdempotencyKey).filter(IdempotencyKey.id == rec_id).one()
        rec.response_body = response
        rec.response_status = status
        rec.status = IdemStatus.COMPLETED
        db.commit()  # money movement + saved response commit together
    except BaseException:
        db.rollback()
        # nothing was processed, so release the key and let the client retry
        db.query(IdempotencyKey).filter(IdempotencyKey.id == rec_id).delete(synchronize_session=False)
        db.commit()
        raise
    notifier.flush(background_tasks)
    return JSONResponse(content=response, status_code=status)
