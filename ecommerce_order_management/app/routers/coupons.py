from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.coupon import Coupon
from app.models.user import UserRole
from app.schemas.coupon import CouponCreate, CouponResponse
from app.auth.dependencies import require_role


router = APIRouter(
    prefix="/coupons",
    tags=["Coupons"]
)


# =========================================================
# CREATE COUPON - ADMIN ONLY
# =========================================================

@router.post(
    "",
    response_model=CouponResponse,
    status_code=201
)
def create_coupon(
    data: CouponCreate,
    db: Session = Depends(get_db),
    user=Depends(require_role(UserRole.Admin))
):
    existing = db.scalar(
        select(Coupon).where(
            Coupon.code == data.code
        )
    )

    if existing:
        raise HTTPException(
            status_code=409,
            detail="Coupon already exists"
        )

    coupon = Coupon(
        **data.model_dump()
    )

    db.add(coupon)
    db.commit()
    db.refresh(coupon)

    return coupon


# =========================================================
# LIST COUPONS - PUBLIC
# =========================================================

@router.get(
    "",
    response_model=list[CouponResponse]
)
def list_coupons(
    skip: int = 0,
    limit: int = 10,
    db: Session = Depends(get_db)
):
    coupons = db.scalars(
        select(Coupon)
        .order_by(Coupon.id.desc())
        .offset(skip)
        .limit(limit)
    ).all()

    return coupons