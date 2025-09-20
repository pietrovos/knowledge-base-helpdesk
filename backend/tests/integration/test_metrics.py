from decimal import Decimal

from app.db import SessionLocal
from app.models import LLMCall, Role
from tests.factories import login, make_user


def test_overview_aggregates_calls_and_drafts(client):
    with SessionLocal() as db:
        db.add_all(
            [
                LLMCall(
                    purpose="draft",
                    provider="anthropic",
                    model="claude-opus-5-5",
                    status="ok",
                    latency_ms=1000,
                    input_tokens=2000,
                    output_tokens=400,
                    cost_usd=Decimal("0.016"),
                ),
                LLMCall(
                    purpose="draft",
                    provider="anthropic",
                    model="claude-opus-5-5",
                    status="ok",
                    latency_ms=3000,
                    input_tokens=1000,
                    output_tokens=200,
                    cost_usd=Decimal("0.008"),
                ),
                LLMCall(
                    purpose="draft",
                    provider="anthropic",
                    model="claude-opus-5-5",
                    status="timeout",
                    latency_ms=45000,
                    error="timed out",
                ),
            ]
        )
        db.commit()
    login(client, make_user(Role.agent))
    assert client.get("/api/metrics/overview").status_code == 403
    login(client, make_user(Role.admin))
    m = client.get("/api/metrics/overview", params={"days": 7}).json()
    t = m["totals"]
    assert (t["calls"], t["errors"], t["input_tokens"], t["output_tokens"]) == (3, 1, 3000, 600)
    assert t["cost_usd"] == 0.024
    assert t["latency_p50_ms"] == 2000  # failures excluded from latency percentiles
    assert len(m["daily"]) == 7 and m["daily"][-1]["calls"] == 3
    assert m["by_status"] == {"ok": 2, "timeout": 1}
    assert m["recent_failures"][0]["error"] == "timed out"


def test_requests_get_a_request_id(client):
    r = client.get("/api/health", headers={"X-Request-ID": "abc123"})
    assert r.headers["X-Request-ID"] == "abc123"
