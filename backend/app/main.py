from fastapi import FastAPI
from sqlalchemy import text

from app.db import engine

app = FastAPI(title="SupportLens API", version="0.1.0")


@app.get("/api/health")
def health() -> dict[str, str]:
    with engine.connect() as conn:
        conn.execute(text("SELECT 1"))
    return {"status": "ok"}
