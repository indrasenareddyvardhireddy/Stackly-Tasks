from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.models.enums import Availability


class CategoryBrief(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    category_name: str


class AgentCreate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    name: str = Field(min_length=2, max_length=100)
    email: EmailStr
    password: str = Field(min_length=8, max_length=72)
    category_ids: List[int] = []
    availability: Availability = Availability.OFFLINE
    max_open_tickets: int = Field(default=10, ge=1, le=1000)


class AgentUpdate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    name: Optional[str] = Field(default=None, min_length=2, max_length=100)
    email: Optional[EmailStr] = None
    category_ids: Optional[List[int]] = None
    availability: Optional[Availability] = None
    max_open_tickets: Optional[int] = Field(default=None, ge=1, le=1000)
    is_active: Optional[bool] = None


class AvailabilityUpdate(BaseModel):
    availability: Availability


class AgentOut(BaseModel):
    user_id: int
    name: str
    email: EmailStr
    categories: List[CategoryBrief]
    availability: Availability
    max_open_tickets: int
    is_active: bool
    created_at: datetime
