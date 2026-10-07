from pydantic import BaseModel, Field
class CategoryCreate(BaseModel):
    name: str = Field(min_length=2, max_length=100)
class CategoryResponse(CategoryCreate):
    id: int
    model_config = {"from_attributes": True}
