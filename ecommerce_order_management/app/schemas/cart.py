from decimal import Decimal
from pydantic import BaseModel, Field
class CartItemCreate(BaseModel):
    product_id: int
    quantity: int = Field(ge=1)
class CartItemUpdate(BaseModel):
    quantity: int = Field(ge=1)
class CartItemResponse(BaseModel):
    id: int
    product_id: int
    product_name: str
    quantity: int
    price: Decimal
    line_total: Decimal
class CartResponse(BaseModel):
    id: int
    items: list[CartItemResponse]
    subtotal: Decimal
