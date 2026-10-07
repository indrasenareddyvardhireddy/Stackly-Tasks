from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, Field

from app.models.coupon import CouponType


class CouponCreate(BaseModel):
    code: str = Field(min_length=1, max_length=50)
    coupon_type: CouponType
    value: Decimal = Field(gt=0)
    minimum_order_value: Decimal = Field(ge=0)
    expires_at: datetime
    usage_limit: int | None = Field(default=None, ge=1)


class CouponResponse(BaseModel):
    id: int
    code: str
    coupon_type: CouponType
    value: Decimal
    minimum_order_value: Decimal
    expires_at: datetime
    usage_limit: int | None
    used_count: int

    model_config = {
        "from_attributes": True
    }