from pydantic import BaseModel, Field
class ReviewCreate(BaseModel):
    rating: int = Field(ge=1, le=5)
    comment: str | None = None
class ReviewUpdate(BaseModel):
    rating: int | None = Field(default=None, ge=1, le=5)
    comment: str | None = None
class ReviewResponse(BaseModel):
    id: int
    product_id: int
    customer_id: int
    rating: int
    comment: str | None
    model_config = {"from_attributes": True}
