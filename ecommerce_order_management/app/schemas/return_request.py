from decimal import Decimal
from pydantic import BaseModel, Field
from app.models.return_request import ReturnStatus
class ReturnCreate(BaseModel):
    reason: str = Field(min_length=3)
class ReturnResponse(BaseModel):
    id: int
    order_id: int
    reason: str
    status: ReturnStatus
    refund_amount: Decimal | None
    rejection_reason: str | None
    model_config = {"from_attributes": True}
class ReturnReject(BaseModel):
    rejection_reason: str = Field(min_length=3)
