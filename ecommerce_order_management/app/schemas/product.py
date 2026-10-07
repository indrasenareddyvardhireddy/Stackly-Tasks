from decimal import Decimal
from pydantic import BaseModel, Field
class ProductCreate(BaseModel):
    name: str = Field(min_length=2, max_length=200)
    sku: str = Field(min_length=2, max_length=80)
    description: str | None = None
    category_id: int
    price: Decimal = Field(gt=0)
    stock_quantity: int = Field(ge=0)
    is_active: bool = True
class ProductUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=200)
    description: str | None = None
    category_id: int | None = None
    price: Decimal | None = Field(default=None, gt=0)
    stock_quantity: int | None = Field(default=None, ge=0)
    is_active: bool | None = None
class ProductResponse(ProductCreate):
    id: int
    average_rating: float = 0
    review_count: int = 0
    model_config = {"from_attributes": True}
