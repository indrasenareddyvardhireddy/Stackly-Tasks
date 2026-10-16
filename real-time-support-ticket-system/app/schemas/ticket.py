from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import Priority, TicketStatus


class TicketCreate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    category_id: int
    subject: str = Field(min_length=5, max_length=150)
    description: str = Field(min_length=10)
    priority: Priority = Priority.MEDIUM


class StatusUpdate(BaseModel):
    status: TicketStatus
    note: Optional[str] = Field(default=None, max_length=500)


class PriorityUpdate(BaseModel):
    priority: Priority


class AssignRequest(BaseModel):
    agent_id: int


class TicketOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    ticket_number: str
    customer_id: int
    category_id: int
    subject: str
    description: str
    priority: Priority
    status: TicketStatus
    assigned_agent_id: Optional[int]
    first_response_due: datetime
    resolution_due: datetime
    first_response_at: Optional[datetime]
    resolved_at: Optional[datetime]
    closed_at: Optional[datetime]
    sla_breached: bool
    reopen_count: int
    created_at: datetime
    updated_at: datetime


class HistoryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    ticket_id: int
    event_type: str
    old_status: Optional[str]
    new_status: Optional[str]
    changed_by: Optional[int]
    note: Optional[str]
    created_at: datetime
