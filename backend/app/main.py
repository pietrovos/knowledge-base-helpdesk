import logging
import time
import uuid

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from sqlalchemy import text

from app.api import (
    auth,
    collections,
    documents,
    drafts,
    gaps,
    groups,
    metrics,
    search,
    system,
    tickets,
    users,
)
from app.db import engine
from app.logging_setup import configure_logging
from app.security import SESSION_COOKIE, decode_token

configure_logging()
log = logging.getLogger("supportlens.http")
app = FastAPI(title="SupportLens API", version="0.1.0")

SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}


@app.middleware("http")
async def request_log(request: Request, call_next):
    request_id = request.headers.get("x-request-id") or uuid.uuid4().hex[:16]
    started = time.perf_counter()
    status = 500
    try:
        response = await call_next(request)
        status = response.status_code
        response.headers["X-Request-ID"] = request_id
        return response
    finally:
        route = request.scope.get("route")
        token = request.cookies.get(SESSION_COOKIE)
        log.info(
            "request",
            extra={
                "event": "http_request",
                "request_id": request_id,
                "method": request.method,
                "route": getattr(route, "path", request.url.path),
                "status": status,
                "latency_ms": round((time.perf_counter() - started) * 1000, 1),
                "user_id": decode_token(token) if token else None,
            },
        )


@app.middleware("http")
async def csrf_guard(request: Request, call_next):
    # The session cookie is SameSite=Lax; additionally require a custom header on state-changing
    # requests. Browsers can't send it cross-origin without a CORS preflight, which we never allow.
    if (
        request.method not in SAFE_METHODS
        and request.url.path.startswith("/api/")
        and request.headers.get("x-requested-with") != "supportlens"
    ):
        return JSONResponse({"detail": "Missing CSRF header"}, status_code=403)
    return await call_next(request)


for module in (
    auth,
    users,
    groups,
    collections,
    documents,
    tickets,
    search,
    drafts,
    gaps,
    system,
    metrics,
):
    app.include_router(module.router)


@app.get("/api/health")
def health() -> dict[str, str]:
    with engine.connect() as conn:
        conn.execute(text("SELECT 1"))
    return {"status": "ok"}
