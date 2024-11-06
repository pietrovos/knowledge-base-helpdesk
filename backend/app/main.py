from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from sqlalchemy import text

from app.api import auth, collections, documents, groups, tickets, users
from app.db import engine

app = FastAPI(title="SupportLens API", version="0.1.0")

SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}


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


for module in (auth, users, groups, collections, documents, tickets):
    app.include_router(module.router)


@app.get("/api/health")
def health() -> dict[str, str]:
    with engine.connect() as conn:
        conn.execute(text("SELECT 1"))
    return {"status": "ok"}
