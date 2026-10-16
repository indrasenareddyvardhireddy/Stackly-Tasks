from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import Role


class MessageCreate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    message: str = Field(min_length=1, max_length=2000)
    is_internal_note: bool = False


class MessageOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    ticket_id: int
    sender_id: int
    sender_role: Role
    message: str
    is_internal_note: bool
    is_read: bool
    created_at: datetime
