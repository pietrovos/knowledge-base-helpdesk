import time
from typing import Literal

from fastapi import APIRouter
from pydantic import BaseModel

from app.api.deps import AdminUser, CurrentUser
from app.config import get_settings
from app.services.resilience import get_chaos_mode, get_redis, llm_breaker, set_chaos_mode
from app.worker.celery_app import HEARTBEAT_KEY

router = APIRouter(prefix="/api/system", tags=["system"])


class LLMStatus(BaseModel):
    provider: str
    model: str
    state: Literal["closed", "open", "half_open"]
    retry_in_seconds: int | None
    recent_failures: int
    last_error: str | None
    simulated_outage: str


class SystemStatus(BaseModel):
    drafting_available: bool
    worker_online: bool
    llm: LLMStatus
    embedding_provider: str
    degraded_reasons: list[str]


@router.get("/status", response_model=SystemStatus)
def status(_: CurrentUser) -> SystemStatus:
    s = get_settings()
    b = llm_breaker().status()
    try:
        beat = get_redis().get(HEARTBEAT_KEY)
        worker_online = beat is not None or s.celery_eager
    except Exception:
        worker_online = s.celery_eager
    chaos = get_chaos_mode()
    reasons = []
    if b.state != "closed":
        reasons.append("The model provider is failing; AI drafts are paused.")
    if not worker_online:
        reasons.append("Background workers are offline; uploads and drafts are queued.")
    if chaos != "none":
        reasons.append(f"A provider outage drill is active ({chaos}).")
    return SystemStatus(
        drafting_available=b.state == "closed" and worker_online,
        worker_online=worker_online,
        llm=LLMStatus(
            provider=s.llm_provider,
            model=s.llm_model if s.llm_provider == "anthropic" else "fake-extractive-1",
            state=b.state,
            retry_in_seconds=max(0, int(b.open_until - time.time())) if b.open_until else None,
            recent_failures=b.failures,
            last_error=b.last_error,
            simulated_outage=chaos,
        ),
        embedding_provider=s.embedding_provider,
        degraded_reasons=reasons,
    )


class ChaosIn(BaseModel):
    mode: Literal["none", "error", "timeout", "slow"]


@router.put("/chaos", response_model=SystemStatus)
def set_chaos(body: ChaosIn, admin: AdminUser) -> SystemStatus:
    set_chaos_mode(body.mode)
    if body.mode == "none":
        llm_breaker().reset()
    return status(admin)
