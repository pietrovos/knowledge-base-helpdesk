"""Usage, latency and cost, aggregated in Postgres from llm_calls and drafts."""

from datetime import UTC, date, datetime, timedelta
from typing import Annotated

from fastapi import APIRouter, Query
from pydantic import BaseModel
from sqlalchemy import Date, case, cast, func, select

from app.api.deps import DB, AdminUser
from app.models import Draft, DraftStatus, LLMCall

router = APIRouter(prefix="/api/metrics", tags=["metrics"])


class Totals(BaseModel):
    calls: int
    errors: int
    error_rate: float | None
    input_tokens: int
    output_tokens: int
    cost_usd: float
    latency_p50_ms: int | None
    latency_p95_ms: int | None


class Day(BaseModel):
    day: date
    calls: int
    errors: int
    cost_usd: float
    input_tokens: int
    output_tokens: int
    latency_p50_ms: int | None
    latency_p95_ms: int | None


class DraftOutcomes(BaseModel):
    total: int
    by_status: dict[str, int]
    evidence_gate_refusals: int
    published: int
    published_unedited: int
    drafts_with_removed_citations: int
    avg_citations_per_answer: float | None
    retrieval_p50_ms: int | None
    retrieval_p95_ms: int | None


class Failure(BaseModel):
    created_at: datetime
    status: str
    model: str
    error: str | None
    latency_ms: int


class Overview(BaseModel):
    days: int
    totals: Totals
    daily: list[Day]
    by_model: list[dict]
    by_status: dict[str, int]
    drafts: DraftOutcomes
    recent_failures: list[Failure]


def _pct(col, p):
    return func.percentile_cont(p).within_group(col.asc())


def _int(x):
    return int(round(x)) if x is not None else None


@router.get("/overview", response_model=Overview)
def overview(db: DB, _: AdminUser, days: Annotated[int, Query(ge=1, le=365)] = 14) -> Overview:
    since = datetime.now(UTC) - timedelta(days=days)
    in_range = LLMCall.created_at >= since
    is_error = case((LLMCall.status != "ok", 1), else_=0)
    ok_latency = case((LLMCall.status == "ok", LLMCall.latency_ms))

    t = db.execute(
        select(
            func.count(),
            func.coalesce(func.sum(is_error), 0),
            func.coalesce(func.sum(LLMCall.input_tokens), 0),
            func.coalesce(func.sum(LLMCall.output_tokens), 0),
            func.coalesce(func.sum(LLMCall.cost_usd), 0),
            _pct(ok_latency, 0.5),
            _pct(ok_latency, 0.95),
        ).where(in_range)
    ).one()
    totals = Totals(
        calls=t[0],
        errors=t[1],
        error_rate=(t[1] / t[0]) if t[0] else None,
        input_tokens=t[2],
        output_tokens=t[3],
        cost_usd=float(t[4]),
        latency_p50_ms=_int(t[5]),
        latency_p95_ms=_int(t[6]),
    )

    day = cast(func.date_trunc("day", LLMCall.created_at), Date).label("day")
    rows = {
        r.day: r
        for r in db.execute(
            select(
                day,
                func.count().label("calls"),
                func.coalesce(func.sum(is_error), 0).label("errors"),
                func.coalesce(func.sum(LLMCall.cost_usd), 0).label("cost"),
                func.coalesce(func.sum(LLMCall.input_tokens), 0).label("tin"),
                func.coalesce(func.sum(LLMCall.output_tokens), 0).label("tout"),
                _pct(ok_latency, 0.5).label("p50"),
                _pct(ok_latency, 0.95).label("p95"),
            )
            .where(in_range)
            .group_by(day)
        )
    }
    today = datetime.now(UTC).date()
    daily = []
    for i in range(days - 1, -1, -1):  # every day in range, including empty ones
        d = today - timedelta(days=i)
        r = rows.get(d)
        daily.append(
            Day(
                day=d,
                calls=r.calls if r else 0,
                errors=r.errors if r else 0,
                cost_usd=float(r.cost) if r else 0.0,
                input_tokens=r.tin if r else 0,
                output_tokens=r.tout if r else 0,
                latency_p50_ms=_int(r.p50) if r else None,
                latency_p95_ms=_int(r.p95) if r else None,
            )
        )

    by_model = [
        {"model": m, "calls": n, "cost_usd": float(c)}
        for m, n, c in db.execute(
            select(LLMCall.model, func.count(), func.coalesce(func.sum(LLMCall.cost_usd), 0))
            .where(in_range)
            .group_by(LLMCall.model)
            .order_by(func.count().desc())
        )
    ]
    by_status = dict(
        db.execute(
            select(LLMCall.status, func.count()).where(in_range).group_by(LLMCall.status)
        ).all()
    )

    d_range = Draft.created_at >= since
    statuses = dict(
        db.execute(select(Draft.status, func.count()).where(d_range).group_by(Draft.status)).all()
    )
    dr = db.execute(
        select(
            func.count(),
            func.count().filter(Draft.decided_by == "evidence_gate"),
            func.count().filter(Draft.status == DraftStatus.published),
            func.count().filter(Draft.status == DraftStatus.published, Draft.was_edited.is_(False)),
            func.count().filter(func.cardinality(Draft.invalid_citation_ids) > 0),
            _pct(Draft.retrieval_ms, 0.5),
            _pct(Draft.retrieval_ms, 0.95),
        ).where(d_range)
    ).one()
    from app.models import DraftSource

    per_answer = (
        select(func.count(DraftSource.id).label("n"))
        .join(Draft, Draft.id == DraftSource.draft_id)
        .where(
            d_range, DraftSource.cited, Draft.status.in_([DraftStatus.ready, DraftStatus.published])
        )
        .group_by(DraftSource.draft_id)
        .subquery()
    )
    avg_cites = db.scalar(select(func.avg(per_answer.c.n)))

    failures = db.scalars(
        select(LLMCall)
        .where(in_range, LLMCall.status != "ok")
        .order_by(LLMCall.created_at.desc())
        .limit(8)
    )
    return Overview(
        days=days,
        totals=totals,
        daily=daily,
        by_model=by_model,
        by_status=by_status,
        drafts=DraftOutcomes(
            total=dr[0],
            by_status={k.value: v for k, v in statuses.items()},
            evidence_gate_refusals=dr[1],
            published=dr[2],
            published_unedited=dr[3],
            drafts_with_removed_citations=dr[4],
            avg_citations_per_answer=round(float(avg_cites), 2) if avg_cites is not None else None,
            retrieval_p50_ms=_int(dr[5]),
            retrieval_p95_ms=_int(dr[6]),
        ),
        recent_failures=[
            Failure(
                created_at=f.created_at,
                status=f.status,
                model=f.model,
                error=f.error,
                latency_ms=f.latency_ms,
            )
            for f in failures
        ],
    )
