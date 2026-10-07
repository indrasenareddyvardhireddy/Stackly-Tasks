from decimal import Decimal
from pydantic import BaseModel, Field
from app.models.payment import PaymentMethod, PaymentResult
class PaymentCreate(BaseModel):
    amount: Decimal = Field(gt=0)
    payment_method: PaymentMethod
    transaction_id: str = Field(min_length=3, max_length=100)
    status: PaymentResult = PaymentResult.Success
class PaymentResponse(PaymentCreate):
    id: int
    order_id: int
    model_config = {"from_attributes": True}
