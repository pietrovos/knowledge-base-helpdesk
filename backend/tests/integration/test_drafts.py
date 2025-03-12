import pytest
from sqlalchemy import select

from app.config import get_settings
from app.db import SessionLocal
from app.models import LLMCall, Role
from app.services import drafting
from app.services.llm import FakeLLM
from tests.factories import add_document, login, make_collection, make_group, make_ticket, make_user

REFUNDS = """# Refund Policy

Customers can request a full refund within 30 days of delivery. Refunds are issued to the original payment method within 5 business days after the returned item is inspected.

## Gift cards

Gift cards are non-refundable and cannot be exchanged for cash.
"""
SECRET = """# Chargeback Playbook

Internal only: when a refund dispute escalates, offer a goodwill credit of up to 40 dollars using code FALCON-GOODWILL before the customer files a chargeback.
"""


@pytest.fixture
def world():
    agent, other = make_user(name="Alex Rivera"), make_user(name="Sam Patel")
    tier1 = make_group("Tier 1", agent, other)
    billing = make_group("Billing", agent)
    policies = make_collection("Policies", groups=(tier1,))
    internal = make_collection("Billing internal", groups=(billing,))
    add_document(policies, "refunds.md", REFUNDS)
    add_document(internal, "chargebacks.md", SECRET)
    FakeLLM.prompts.clear()
    return {
        "agent": agent,
        "other": other,
        "billing": billing,
        "policies": policies,
        "internal": internal,
    }


@pytest.fixture
def fake_mode(monkeypatch):
    def set_mode(mode):
        monkeypatch.setattr(get_settings(), "fake_llm_mode", mode)

    return set_mode


def ask(client, ticket_id, question=None):
    r = client.post(
        f"/api/tickets/{ticket_id}/drafts", json={"question": question} if question else {}
    )
    assert r.status_code == 202, r.text
    return client.get(f"/api/drafts/{r.json()['id']}").json()


def test_answer_is_grounded_and_cites_retrieved_chunks(world, client):
    login(client, world["agent"])
    t = make_ticket(
        "Refund timing", "How long until my refund reaches my card after you get the return?"
    )
    d = ask(client, t.id)
    assert d["status"] == "ready", d
    assert d["reply"].startswith("Hi Casey")
    retrieved = {s["chunk_id"] for s in d["sources"]}
    cited = {s["chunk_id"] for s in d["sources"] if s["cited"]}
    assert cited and cited <= retrieved
    assert all(f"[{c}]" in d["reply"] for c in cited)
    assert "5 business days" in d["reply"]
    with SessionLocal() as db:
        call = db.scalar(select(LLMCall).where(LLMCall.draft_id == d["id"]))
    assert call.status == "ok" and call.purpose == "draft" and call.input_tokens > 0


def test_unrelated_question_is_stopped_by_evidence_gate(world, client):
    login(client, world["agent"])
    t = make_ticket("Router", "My wifi router keeps dropping the 5GHz band at night.")
    d = ask(client, t.id)
    assert d["status"] == "insufficient_evidence"
    assert d["decided_by"] == "evidence_gate"
    assert FakeLLM.prompts == []  # the model was never called


def test_model_can_decline_when_sources_dont_answer(world, client):
    login(client, world["agent"])
    t = make_ticket("Refund", "Refund question")
    # Passes the retrieval gate (it is about refunds) but no passage answers it.
    d = ask(client, t.id, "Is there a refund policy for warranty repairs?")
    assert d["best_similarity"] >= 0.15
    assert d["status"] == "insufficient_evidence"
    assert d["decided_by"] == "model"
    assert d["missing_information"]


def test_hallucinated_citation_is_stripped_and_flagged(world, client, fake_mode):
    fake_mode("bad_citations")
    login(client, world["agent"])
    t = make_ticket(
        "Refund timing", "How long until my refund reaches my card after you get the return?"
    )
    d = ask(client, t.id)
    assert d["status"] == "ready"
    assert d["invalid_citation_ids"] == [999999999]
    assert "[999999999]" not in d["reply"]


def test_uncited_answer_is_withheld(world, client, fake_mode):
    fake_mode("uncited")
    login(client, world["agent"])
    t = make_ticket(
        "Refund timing", "How long until my refund reaches my card after you get the return?"
    )
    d = ask(client, t.id)
    assert d["status"] == "insufficient_evidence"
    assert d["decided_by"] == "validator"
    assert d["reply"] == ""


def test_provider_failure_fails_draft_not_ticket(world, client, fake_mode):
    fake_mode("error")
    login(client, world["agent"])
    t = make_ticket(
        "Refund timing", "How long until my refund reaches my card after you get the return?"
    )
    d = ask(client, t.id)
    assert (d["status"], d["error_kind"]) == ("failed", "unavailable")
    assert client.get(f"/api/tickets/{t.id}").status_code == 200
    assert (
        client.post(f"/api/tickets/{t.id}/messages", json={"body": "Manual reply"}).status_code
        == 201
    )
    with SessionLocal() as db:
        assert db.scalar(select(LLMCall.status).where(LLMCall.draft_id == d["id"])) == "error"


def test_unreadable_content_never_reaches_the_prompt(world, client):
    """The decisive leak test: a user outside Billing asks a question that matches the restricted
    playbook almost word for word. The restricted text must not appear in any prompt."""
    login(client, world["other"])
    t = make_ticket(
        "Refund dispute",
        "My refund dispute escalated. Can you offer a goodwill credit before I file a chargeback?",
    )
    ask(client, t.id)
    ask(client, t.id, "goodwill credit code FALCON-GOODWILL chargeback 40 dollars")
    assert FakeLLM.prompts, "the model should have been called with the readable refund policy"
    for prompt in FakeLLM.prompts:
        sources = prompt.split("</sources>")[0]
        assert "Chargeback Playbook" not in sources
        assert "Internal only" not in sources
    assert not any("FALCON" in p and "Internal only" in p for p in FakeLLM.prompts)
    # whereas a Billing member does get it
    FakeLLM.prompts.clear()
    login(client, world["agent"])
    ask(client, t.id)
    assert any("FALCON-GOODWILL" in p for p in FakeLLM.prompts)


def test_revocation_between_request_and_generation_is_honoured(world, client, monkeypatch):
    monkeypatch.setattr(drafting, "enqueue", lambda draft_id: True)  # hold the job
    login(client, world["agent"])
    t = make_ticket("Refund dispute", "Can you offer a goodwill credit before I file a chargeback?")
    draft_id = client.post(f"/api/tickets/{t.id}/drafts", json={}).json()["id"]
    admin = make_user(Role.admin)
    login(client, admin)
    client.delete(f"/api/groups/{world['billing'].id}/members/{world['agent'].id}")
    drafting.run_draft(draft_id)
    assert not any("Internal only" in p for p in FakeLLM.prompts)


def test_evidence_viewer_and_access_rechecks(world, client, make_client):
    login(client, world["agent"])
    t = make_ticket(
        "Refund dispute",
        "My refund dispute escalated. Can you offer a goodwill credit before I file a chargeback?",
    )
    d = ask(client, t.id)
    secret_src = next(s for s in d["sources"] if "FALCON" in (s["text"] or ""))
    ev = client.get(f"/api/drafts/{d['id']}/evidence/{secret_src['chunk_id']}").json()
    assert "FALCON-GOODWILL" in ev["source"]["text"]
    assert ev["collection_name"] == "Billing internal"

    # A teammate without Billing access sees the same ticket draft with the passage redacted.
    other = make_client()
    login(other, world["other"])
    seen = other.get(f"/api/drafts/{d['id']}").json()
    redacted = next(s for s in seen["sources"] if s["chunk_id"] == secret_src["chunk_id"])
    assert redacted["text"] is None and redacted["accessible"] is False
    assert other.get(f"/api/drafts/{d['id']}/evidence/{secret_src['chunk_id']}").status_code == 403

    # Citations must reference retrieved chunks only.
    assert client.get(f"/api/drafts/{d['id']}/evidence/123456789").status_code == 404


def test_evidence_shows_retired_when_document_updated(world, client):
    login(client, world["agent"])
    t = make_ticket(
        "Refund timing", "How long until my refund reaches my card after you get the return?"
    )
    d = ask(client, t.id)
    cited = next(s for s in d["sources"] if s["cited"])
    add_document(
        world["policies"], "refunds.md", REFUNDS.replace("5 business days", "10 business days")
    )
    ev = client.get(f"/api/drafts/{d['id']}/evidence/{cited['chunk_id']}").json()
    assert ev["source"]["live"] is False
    assert "5 business days" in ev["source"]["text"]  # still exactly what the model saw


def test_knowledge_gap_from_insufficient_draft_is_idempotent(world, client):
    login(client, world["agent"])
    t = make_ticket("Router", "My wifi router keeps dropping the 5GHz band at night.")
    d = ask(client, t.id)
    g1 = client.post("/api/knowledge-gaps", json={"draft_id": d["id"]})
    g2 = client.post("/api/knowledge-gaps", json={"draft_id": d["id"]})
    assert g1.status_code == g2.status_code == 201
    assert g1.json()["id"] == g2.json()["id"]
    assert g1.json()["ticket_id"] == t.id
    assert client.get(f"/api/drafts/{d['id']}").json()["knowledge_gap_id"] == g1.json()["id"]
    assert [g["id"] for g in client.get("/api/knowledge-gaps").json()] == [g1.json()["id"]]
    events = client.get(f"/api/tickets/{t.id}").json()["events"]
    assert events[-1]["kind"] == "knowledge_gap_created"


def test_deactivated_requester_draft_fails_closed(world, client, monkeypatch):
    monkeypatch.setattr(drafting, "enqueue", lambda draft_id: True)
    login(client, world["agent"])
    t = make_ticket()
    draft_id = client.post(f"/api/tickets/{t.id}/drafts", json={}).json()["id"]
    login(client, make_user(Role.admin))
    client.patch(f"/api/users/{world['agent'].id}", json={"is_active": False})
    drafting.run_draft(draft_id)
    d = client.get(f"/api/drafts/{draft_id}").json()
    assert (d["status"], d["error_kind"]) == ("failed", "forbidden")
    assert FakeLLM.prompts == []
