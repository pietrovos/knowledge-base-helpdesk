from fastapi import APIRouter, HTTPException
from sqlalchemy import select

from app.api.deps import DB, CurrentUser
from app.models import Draft, GapStatus, KnowledgeGap, Ticket
from app.schemas.drafts import GapCreate, GapOut
from app.services import tickets as ticket_svc

router = APIRouter(prefix="/api/knowledge-gaps", tags=["knowledge gaps"])


@router.post("", response_model=GapOut, status_code=201)
def create_gap(body: GapCreate, db: DB, user: CurrentUser) -> KnowledgeGap:
    draft = db.get(Draft, body.draft_id) if body.draft_id else None
    if body.draft_id and not draft:
        raise HTTPException(404, "Draft not found")
    if draft:
        existing = db.scalar(select(KnowledgeGap).where(KnowledgeGap.draft_id == draft.id))
        if existing:
            return existing  # idempotent: one gap per draft
    question = (body.question or (draft.question if draft else "")).strip()
    if not question:
        raise HTTPException(422, "A question is required")
    ticket_id = draft.ticket_id if draft else body.ticket_id
    gap = KnowledgeGap(
        ticket_id=ticket_id,
        draft_id=draft.id if draft else None,
        question=question,
        missing_information=(
            body.missing_information or (draft.missing_information if draft else "")
        ),
        created_by_id=user.id,
    )
    db.add(gap)
    if ticket_id and (ticket := db.get(Ticket, ticket_id)):
        db.flush()
        ticket_svc.record(db, ticket, user, "knowledge_gap_created", gap_id=gap.id)
    db.commit()
    return gap


@router.get("", response_model=list[GapOut])
def list_gaps(
    db: DB, user: CurrentUser, status: GapStatus | None = GapStatus.open
) -> list[KnowledgeGap]:
    q = select(KnowledgeGap).order_by(KnowledgeGap.created_at.desc())
    if status:
        q = q.where(KnowledgeGap.status == status)
    return list(db.scalars(q.limit(200)))
