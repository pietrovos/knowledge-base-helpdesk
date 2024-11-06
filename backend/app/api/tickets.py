from typing import Annotated, Literal

from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import func, or_, select
from sqlalchemy.dialects.postgresql import distinct_on

from app.api.deps import DB, CurrentUser
from app.models import AuthorType, Ticket, TicketMessage, TicketStatus, User
from app.schemas.tickets import (
    MessageCreate,
    MessageOut,
    TicketCreate,
    TicketDetail,
    TicketPage,
    TicketSummary,
    TicketUpdate,
)
from app.services import tickets as svc

router = APIRouter(prefix="/api/tickets", tags=["tickets"])

ACTIVE = (TicketStatus.open, TicketStatus.pending, TicketStatus.escalated)
View = Literal[
    "active", "mine", "unassigned", "open", "pending", "escalated", "resolved", "closed", "all"
]


def _view_filter(view: View, user):
    match view:
        case "active":
            return Ticket.status.in_(ACTIVE)
        case "mine":
            return (Ticket.assignee_id == user.id) & Ticket.status.in_(ACTIVE)
        case "unassigned":
            return Ticket.assignee_id.is_(None) & Ticket.status.in_(ACTIVE)
        case "all":
            return True
        case _:
            return Ticket.status == TicketStatus(view)


def _summary(t: Ticket, preview: str = "", count: int = 0) -> TicketSummary:
    return TicketSummary.model_validate(t).model_copy(
        update={"preview": preview, "message_count": count}
    )


def get_ticket_or_404(db, ticket_id: int) -> Ticket:
    t = db.get(Ticket, ticket_id)
    if not t:
        raise HTTPException(404, "Ticket not found")
    return t


@router.get("", response_model=TicketPage)
def list_tickets(
    db: DB,
    user: CurrentUser,
    view: View = "active",
    q: Annotated[str | None, Query(max_length=200)] = None,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 25,
) -> TicketPage:
    where = [_view_filter(view, user)]
    if q:
        like = f"%{q}%"
        where.append(
            or_(
                Ticket.subject.ilike(like),
                Ticket.customer_email.ilike(like),
                Ticket.customer_name.ilike(like),
            )
        )
    total = db.scalar(select(func.count()).select_from(Ticket).where(*where))
    # Postgres orders enums by declaration (low → urgent): most urgent first, then most recent.
    rows = db.scalars(
        select(Ticket)
        .where(*where)
        .order_by(Ticket.priority.desc(), Ticket.updated_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()
    ids = [t.id for t in rows]
    first = (
        dict(
            db.execute(
                select(TicketMessage.ticket_id, TicketMessage.body)
                .where(
                    TicketMessage.ticket_id.in_(ids),
                    TicketMessage.author_type == AuthorType.customer,
                )
                .ext(distinct_on(TicketMessage.ticket_id))
                .order_by(TicketMessage.ticket_id, TicketMessage.id.desc())
            ).all()
        )
        if ids
        else {}
    )
    counts = (
        dict(
            db.execute(
                select(TicketMessage.ticket_id, func.count())
                .where(TicketMessage.ticket_id.in_(ids))
                .group_by(TicketMessage.ticket_id)
            ).all()
        )
        if ids
        else {}
    )
    return TicketPage(
        items=[_summary(t, (first.get(t.id) or "")[:160], counts.get(t.id, 0)) for t in rows],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/counts", response_model=dict[str, int])
def counts(db: DB, user: CurrentUser) -> dict[str, int]:
    views: list[View] = ["active", "mine", "unassigned", "pending", "escalated"]
    return {
        v: db.scalar(select(func.count()).select_from(Ticket).where(_view_filter(v, user)))
        for v in views
    }


@router.post("", response_model=TicketDetail, status_code=201)
def create_ticket(body: TicketCreate, db: DB, user: CurrentUser) -> Ticket:
    t = Ticket(
        subject=body.subject,
        customer_name=body.customer_name,
        customer_email=body.customer_email,
        priority=body.priority,
    )
    db.add(t)
    db.flush()
    db.add(TicketMessage(ticket_id=t.id, author_type=AuthorType.customer, body=body.body))
    svc.record(db, t, user, "created")
    db.commit()
    return t


@router.get("/{ticket_id}", response_model=TicketDetail)
def get_ticket(ticket_id: int, db: DB, user: CurrentUser) -> TicketDetail:
    t = get_ticket_or_404(db, ticket_id)
    preview = next(
        (m.body for m in reversed(t.messages) if m.author_type == AuthorType.customer), ""
    )
    return TicketDetail.model_validate(t).model_copy(
        update={"preview": preview[:160], "message_count": len(t.messages)}
    )


@router.patch("/{ticket_id}", response_model=TicketDetail)
def update_ticket(ticket_id: int, body: TicketUpdate, db: DB, user: CurrentUser) -> TicketDetail:
    t = get_ticket_or_404(db, ticket_id)
    if body.status is not None:
        if body.status == TicketStatus.escalated and not (body.escalation_reason or "").strip():
            raise HTTPException(422, "Escalating a ticket requires a reason")
        svc.set_status(db, t, user, body.status, body.escalation_reason)
    if body.priority is not None and body.priority != t.priority:
        svc.record(
            db, t, user, "priority_changed", **{"from": t.priority.value, "to": body.priority.value}
        )
        t.priority = body.priority
    if body.unassign and t.assignee_id is not None:
        svc.record(db, t, user, "unassigned")
        t.assignee_id = None
    elif body.assignee_id is not None and body.assignee_id != t.assignee_id:
        assignee = db.get(User, body.assignee_id)
        if not assignee or not assignee.is_active:
            raise HTTPException(422, "Assignee must be an active user")
        svc.record(db, t, user, "assigned", assignee_id=assignee.id, assignee_name=assignee.name)
        t.assignee_id = assignee.id
    db.commit()
    db.refresh(t)
    return get_ticket(ticket_id, db, user)


@router.post("/{ticket_id}/messages", response_model=MessageOut, status_code=201)
def add_message(ticket_id: int, body: MessageCreate, db: DB, user: CurrentUser) -> TicketMessage:
    t = get_ticket_or_404(db, ticket_id)
    msg = svc.add_agent_message(db, t, user, body.body, internal=body.is_internal)
    if body.status is not None:
        svc.set_status(db, t, user, body.status)
    t.updated_at = func.now()
    db.commit()
    return msg
