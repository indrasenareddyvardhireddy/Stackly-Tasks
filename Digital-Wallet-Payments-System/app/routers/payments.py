import io
from typing import Optional

import qrcode
from fastapi import APIRouter, BackgroundTasks, Depends, Header, Request, Response
from sqlalchemy.orm import Session

from app.auth.dependencies import require_merchant, require_user
from app.database import get_db
from app.models import MerchantPayment, Transaction, User
from app.schemas.common import Page, paginated
from app.schemas.wallet import MerchantPaymentRequest, RefundRequest
from app.services import money
from app.services.idempotency import run_idempotent
from app.utils.common import jsonable, mask_phone

router = APIRouter(tags=["Merchant Payments"])
IDEM = Header(None, alias="Idempotency-Key", description="Unique value (e.g. UUID) created by the client")


@router.get("/merchants/me/qr", response_class=Response, responses={200: {"content": {"image/png": {}}}})
def my_qr(merchant: User = Depends(require_merchant)):
    code = merchant.merchant.merchant_code
    img = qrcode.make(code)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return Response(content=buf.getvalue(), media_type="image/png",
                    headers={"X-Merchant-Code": code, "Content-Disposition": f'inline; filename="{code}.png"'})


@router.post("/payments/merchant", status_code=201)
def pay_merchant(body: MerchantPaymentRequest, request: Request, background_tasks: BackgroundTasks,
                 idempotency_key: Optional[str] = IDEM, user: User = Depends(require_user), db: Session = Depends(get_db)):
    return run_idempotent(db, user, request, idempotency_key, body.model_dump(mode="json"),
                          lambda n: money.merchant_payment(db, user, body, n), background_tasks)


@router.post("/payments/{transaction_ref}/refund", status_code=201)
def refund(transaction_ref: str, body: RefundRequest, request: Request, background_tasks: BackgroundTasks,
           idempotency_key: Optional[str] = IDEM, merchant: User = Depends(require_merchant),
           db: Session = Depends(get_db)):
    return run_idempotent(db, merchant, request, idempotency_key, body.model_dump(mode="json"),
                          lambda n: money.refund_payment(db, merchant, transaction_ref, body, n), background_tasks)


@router.get("/merchants/me/payments")
def my_payments(page: Page = Depends(), merchant: User = Depends(require_merchant), db: Session = Depends(get_db)):
    q = db.query(MerchantPayment).filter(MerchantPayment.merchant_id == merchant.merchant.id)
    total = q.count()
    rows = q.order_by(MerchantPayment.id.desc()).offset(page.skip).limit(page.limit).all()
    items = [{"transaction_ref": p.transaction.transaction_ref, "customer": p.user.full_name,
              "customer_phone": mask_phone(p.user.phone), "amount": p.amount, "platform_fee": p.fee_amount,
              "net_amount": p.amount - p.fee_amount, "refunded_amount": p.refunded_amount,
              "status": p.transaction.status, "date": p.transaction.created_at} for p in rows]
    return paginated(jsonable(items), total, page)
