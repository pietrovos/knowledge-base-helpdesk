from sqlalchemy.orm import Session

from app.models import AuthorType, Ticket, TicketEvent, TicketMessage, TicketStatus, User


def record(db: Session, ticket: Ticket, actor: User | None, kind: str, **data) -> None:
    db.add(
        TicketEvent(ticket_id=ticket.id, actor_id=actor.id if actor else None, kind=kind, data=data)
    )


def set_status(
    db: Session, ticket: Ticket, actor: User | None, status: TicketStatus, reason: str | None = None
) -> None:
    if ticket.status == status:
        return
    record(
        db,
        ticket,
        actor,
        "status_changed",
        **{"from": ticket.status.value, "to": status.value},
        **({"reason": reason} if reason else {}),
    )
    ticket.status = status
    ticket.escalation_reason = reason if status == TicketStatus.escalated else None


def add_agent_message(
    db: Session,
    ticket: Ticket,
    author: User,
    body: str,
    *,
    internal: bool = False,
    draft_id: int | None = None,
) -> TicketMessage:
    msg = TicketMessage(
        ticket_id=ticket.id,
        author_type=AuthorType.agent,
        author_id=author.id,
        body=body,
        is_internal=internal,
        draft_id=draft_id,
    )
    db.add(msg)
    if not internal and ticket.assignee_id is None:
        ticket.assignee_id = author.id  # replying to an unassigned ticket takes ownership
        record(db, ticket, author, "assigned", assignee_id=author.id, assignee_name=author.name)
    return msg
