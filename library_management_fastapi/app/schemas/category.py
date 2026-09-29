from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class CategoryCreate(BaseModel):

    category_name: str = Field(
        ...,
        min_length=1,
        max_length=100
    )

    description: Optional[str] = None


class CategoryUpdate(BaseModel):

    category_name: str = Field(
        ...,
        min_length=1,
        max_length=100
    )

    description: Optional[str] = None


class CategoryResponse(BaseModel):

    category_id: int
    category_name: str
    description: Optional[str] = None

    model_config = ConfigDict(
        from_attributes=True
    )