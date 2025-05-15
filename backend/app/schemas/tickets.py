from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.models import AuthorType, TicketPriority, TicketStatus
from app.schemas.identity import UserRef


class ORM(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class TicketSummary(ORM):
    id: int
    subject: str
    customer_name: str
    customer_email: str
    status: TicketStatus
    priority: TicketPriority
    assignee: UserRef | None
    created_at: datetime
    updated_at: datetime
    escalation_reason: str | None = None
    preview: str = ""
    message_count: int = 0


class MessageOut(ORM):
    id: int
    author_type: AuthorType
    author: UserRef | None
    body: str
    is_internal: bool
    draft_id: int | None
    created_at: datetime


class EventOut(ORM):
    id: int
    kind: str
    actor: UserRef | None
    data: dict[str, Any]
    created_at: datetime


class TicketDetail(TicketSummary):
    messages: list[MessageOut]
    events: list[EventOut]


class TicketPage(BaseModel):
    items: list[TicketSummary]
    total: int
    page: int
    page_size: int


class TicketCreate(BaseModel):
    subject: str = Field(min_length=1, max_length=200)
    customer_name: str = Field(min_length=1, max_length=120)
    customer_email: EmailStr
    body: str = Field(min_length=1, max_length=20_000)
    priority: TicketPriority = TicketPriority.normal


class TicketUpdate(BaseModel):
    status: TicketStatus | None = None
    priority: TicketPriority | None = None
    assignee_id: int | None = None
    unassign: bool = False
    escalation_reason: str | None = Field(default=None, max_length=2000)


class MessageCreate(BaseModel):
    body: str = Field(min_length=1, max_length=20_000)
    is_internal: bool = False
    # Optionally set the ticket status in the same action ("reply and mark pending").
    status: TicketStatus | None = None
