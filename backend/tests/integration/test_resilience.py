import time

import pytest
import redis

from app.config import get_settings
from app.models import Role
from app.services.llm import DraftRequest, FakeLLM, LLMError, Source
from app.services.resilience import CircuitBreaker, ResilientLLM, get_redis
from tests.factories import add_document, login, make_collection, make_group, make_ticket, make_user

REQ = DraftRequest(
    "Casey",
    "Refund",
    "How long do refunds take after the return?",
    [Source(1, "Refund Policy", "", "Refunds take 5 business days after the return is inspected.")],
)


class Clock:
    def __init__(self):
        self.t = 1_000.0

    def __call__(self):
        return self.t


def unavailable():
    return LLMError("unavailable", "503")


def test_breaker_opens_after_threshold_and_fails_fast():
    clock = Clock()
    b = CircuitBreaker("t", threshold=3, cooldown=30, clock=clock)
    for _ in range(2):
        b.before_call()
        b.record_failure(unavailable())
    assert b.status().state == "closed"
    b.record_failure(unavailable())
    assert b.status().state == "open"
    with pytest.raises(LLMError) as e:
        b.before_call()
    assert e.value.kind == "circuit_open"


def test_request_specific_errors_do_not_trip():
    b = CircuitBreaker("t", threshold=1, clock=Clock())
    b.record_failure(LLMError("refused", "declined"))
    b.record_failure(LLMError("bad_output", "truncated"))
    assert b.status().state == "closed"


def test_half_open_allows_one_probe_then_closes_on_success():
    clock = Clock()
    b = CircuitBreaker("t", threshold=1, cooldown=30, clock=clock)
    b.record_failure(unavailable())
    clock.t += 31
    assert b.status().state == "half_open"
    b.before_call()  # the probe
    with pytest.raises(LLMError):
        b.before_call()  # everyone else still fails fast
    b.record_success()
    assert b.status().state == "closed"
    b.before_call()


def test_failed_probe_reopens():
    clock = Clock()
    b = CircuitBreaker("t", threshold=1, cooldown=30, clock=clock)
    b.record_failure(unavailable())
    clock.t += 31
    b.before_call()
    b.record_failure(unavailable())
    assert b.status().state == "open"
    assert b.status().open_until == pytest.approx(clock.t + 30)


def test_breaker_fails_open_when_redis_is_down():
    dead = redis.Redis.from_url(
        "redis://localhost:1/0", socket_connect_timeout=0.1, socket_timeout=0.1
    )
    b = CircuitBreaker("t", threshold=1, r=dead)
    b.record_failure(unavailable())  # must not raise
    assert b.status().state == "closed"
    b.before_call()  # drafting still allowed


def test_deadline_bounds_a_hanging_provider():
    llm = ResilientLLM(FakeLLM("slow"), CircuitBreaker("t"), deadline=0.3)
    started = time.perf_counter()
    with pytest.raises(LLMError) as e:
        llm.draft(REQ)
    assert e.value.kind == "timeout"
    assert time.perf_counter() - started < 1.0


def test_success_resets_failure_count():
    b = CircuitBreaker("t", threshold=3)
    llm = ResilientLLM(FakeLLM("ok"), b, deadline=5)
    b.record_failure(unavailable())
    b.record_failure(unavailable())
    llm.draft(REQ)
    assert b.status().failures == 0


@pytest.fixture
def agent_setup(client):
    agent = make_user(name="Alex")
    team = make_group("Team", agent)
    add_document(
        make_collection("Policies", groups=(team,)),
        "refunds.md",
        "# Refunds\n\nRefunds are issued within 5 business days after the returned item is inspected.\n",
    )
    login(client, agent)
    FakeLLM.prompts.clear()
    return client


def draft(client, ticket_id):
    return client.post(f"/api/tickets/{ticket_id}/drafts", json={})


def test_provider_outage_end_to_end(agent_setup, monkeypatch):
    client = agent_setup
    monkeypatch.setattr(get_settings(), "fake_llm_mode", "error")
    t = make_ticket(
        "Refund timing", "How long until my refund arrives after the returned item is inspected?"
    )
    statuses = [
        client.get(f"/api/drafts/{draft(client, t.id).json()['id']}").json()["error_kind"]
        for _ in range(3)
    ]
    assert statuses == ["unavailable"] * 3
    calls_before = len(FakeLLM.prompts)

    # Circuit is open now: requests fail fast without touching the provider.
    r = draft(client, t.id)
    assert r.status_code == 503
    assert "fully usable" in r.json()["detail"]
    assert len(FakeLLM.prompts) == calls_before

    status = client.get("/api/system/status").json()
    assert status["llm"]["state"] == "open"
    assert status["drafting_available"] is False
    assert status["degraded_reasons"]

    # Everything else keeps working.
    assert client.get("/api/tickets").status_code == 200
    assert (
        client.post(
            f"/api/tickets/{t.id}/messages", json={"body": "Manual reply while degraded"}
        ).status_code
        == 201
    )
    assert client.patch(f"/api/tickets/{t.id}", json={"status": "pending"}).status_code == 200
    assert client.get("/api/search", params={"q": "refund"}).json()["hits"]


def test_recovery_after_cooldown(agent_setup, monkeypatch):
    client = agent_setup
    from app.services import resilience

    b = resilience.llm_breaker()
    for _ in range(3):
        b.record_failure(unavailable())
    assert draft(client, make_ticket().id).status_code == 503
    # Cooldown elapses: the next request is the half-open probe, and the provider is healthy.
    get_redis().set("cb:llm:open_until", time.time() - 1)
    t = make_ticket(
        "Refund timing", "How long until my refund arrives after the returned item is inspected?"
    )
    d = client.get(f"/api/drafts/{draft(client, t.id).json()['id']}").json()
    assert d["status"] == "ready"
    assert client.get("/api/system/status").json()["llm"]["state"] == "closed"


def test_outage_drill_switch_is_admin_only(agent_setup, make_client):
    client = agent_setup
    assert client.put("/api/system/chaos", json={"mode": "error"}).status_code == 403
    admin = make_client()
    login(admin, make_user(Role.admin))
    assert (
        admin.put("/api/system/chaos", json={"mode": "error"}).json()["llm"]["simulated_outage"]
        == "error"
    )
    t = make_ticket(
        "Refund timing", "How long until my refund arrives after the returned item is inspected?"
    )
    d = client.get(f"/api/drafts/{draft(client, t.id).json()['id']}").json()
    assert d["status"] == "failed" and "simulated outage" in d["error"]
    assert FakeLLM.prompts == []  # the drill fails before the provider is called
    status = admin.put("/api/system/chaos", json={"mode": "none"}).json()
    assert status["llm"]["simulated_outage"] == "none" and status["llm"]["state"] == "closed"


def test_timeouts_are_recorded_and_trip_the_breaker(agent_setup, monkeypatch, make_client):
    client = agent_setup
    monkeypatch.setattr(
        get_settings(), "llm_timeout_seconds", 0.2
    )  # deadline = 5.2s; chaos sleeps past it
    admin = make_client()
    login(admin, make_user(Role.admin))
    admin.put("/api/system/chaos", json={"mode": "timeout"})
    from app.services import resilience

    monkeypatch.setattr(
        resilience,
        "get_resilient_llm",
        lambda: ResilientLLM(FakeLLM(), resilience.llm_breaker(), deadline=0.2),
    )
    t = make_ticket(
        "Refund timing", "How long until my refund arrives after the returned item is inspected?"
    )
    d = client.get(f"/api/drafts/{draft(client, t.id).json()['id']}").json()
    assert (d["status"], d["error_kind"]) == ("failed", "timeout")
    from sqlalchemy import select

    from app.db import SessionLocal
    from app.models import LLMCall

    with SessionLocal() as db:
        assert db.scalar(select(LLMCall.status).where(LLMCall.draft_id == d["id"])) == "timeout"
