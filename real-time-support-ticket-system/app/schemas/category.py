from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.models.enums import Priority


class CategoryCreate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    category_name: str = Field(min_length=2, max_length=100)
    description: Optional[str] = None
    is_active: bool = True


class CategoryUpdate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    category_name: Optional[str] = Field(default=None, min_length=2, max_length=100)
    description: Optional[str] = None
    is_active: Optional[bool] = None


class CategoryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    category_name: str
    description: Optional[str]
    is_active: bool
    created_at: datetime


class SLAPolicyUpdate(BaseModel):
    first_response_minutes: int = Field(gt=0)
    resolution_minutes: int = Field(gt=0)

    @model_validator(mode="after")
    def _check(self):
        if self.resolution_minutes < self.first_response_minutes:
            raise ValueError("resolution_minutes must be >= first_response_minutes")
        return self


class SLAPolicyOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    priority: Priority
    first_response_minutes: int
    resolution_minutes: int
