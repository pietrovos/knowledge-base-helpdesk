import pytest

from app.models import Role
from tests.factories import add_document, login, make_collection, make_group, make_ticket, make_user

REFUNDS = """# Refund Policy

Refunds are issued to the original payment method within 5 business days after the returned item is inspected.
"""


@pytest.fixture
def agent_client(client):
    agent = make_user(name="Alex Rivera")
    team = make_group("Team", agent)
    policies = make_collection("Policies", groups=(team,))
    add_document(policies, "refunds.md", REFUNDS)
    login(client, agent)
    return client


def ready_draft(client):
    t = make_ticket(
        "Refund timing", "How long until my refund reaches my card after you get the return?"
    )
    d = client.post(f"/api/tickets/{t.id}/drafts", json={}).json()
    d = client.get(f"/api/drafts/{d['id']}").json()
    assert d["status"] == "ready"
    return t, d


def test_publish_unedited_draft_strips_markers(agent_client):
    t, d = ready_draft(agent_client)
    r = agent_client.post(
        f"/api/drafts/{d['id']}/publish", json={"text": d["reply"], "ticket_status": "pending"}
    )
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "published" and body["was_edited"] is False
    assert "[" not in body["published_text"]
    ticket = agent_client.get(f"/api/tickets/{t.id}").json()
    sent = ticket["messages"][-1]
    assert (sent["author_type"], sent["draft_id"], sent["body"]) == (
        "agent",
        d["id"],
        body["published_text"],
    )
    assert ticket["status"] == "pending"
    assert ticket["assignee"]["name"] == "Alex Rivera"
    published = next(e for e in ticket["events"] if e["kind"] == "draft_published")
    assert published["data"]["edited"] is False and published["data"]["citations"]


def test_edited_publish_is_recorded_as_edited(agent_client):
    _, d = ready_draft(agent_client)
    r = agent_client.post(
        f"/api/drafts/{d['id']}/publish", json={"text": d["reply"] + "\n\nBest,\nAlex"}
    )
    assert r.json()["was_edited"] is True


def test_cannot_publish_twice_or_non_ready(agent_client):
    _, d = ready_draft(agent_client)
    assert (
        agent_client.post(f"/api/drafts/{d['id']}/publish", json={"text": "ok"}).status_code == 200
    )
    assert (
        agent_client.post(f"/api/drafts/{d['id']}/publish", json={"text": "ok"}).status_code == 409
    )
    t = make_ticket("Router", "My wifi router keeps dropping the 5GHz band at night.")
    gap_draft = agent_client.post(f"/api/tickets/{t.id}/drafts", json={}).json()
    assert (
        agent_client.post(
            f"/api/drafts/{gap_draft['id']}/publish", json={"text": "guess"}
        ).status_code
        == 409
    )


def test_empty_after_stripping_is_rejected(agent_client):
    _, d = ready_draft(agent_client)
    assert (
        agent_client.post(f"/api/drafts/{d['id']}/publish", json={"text": "[12] [13]"}).status_code
        == 422
    )


def test_escalation_queue_shows_reason(agent_client):
    t = make_ticket("Legal", "I will sue")
    agent_client.patch(
        f"/api/tickets/{t.id}", json={"status": "escalated", "escalation_reason": "Legal threat"}
    )
    items = agent_client.get("/api/tickets", params={"view": "escalated"}).json()["items"]
    assert [(i["id"], i["escalation_reason"]) for i in items] == [(t.id, "Legal threat")]


def test_knowledge_gap_lifecycle(agent_client, make_client):
    t = make_ticket("Router", "My wifi router keeps dropping the 5GHz band at night.")
    d = agent_client.post(f"/api/tickets/{t.id}/drafts", json={}).json()
    gap = agent_client.post("/api/knowledge-gaps", json={"draft_id": d["id"]}).json()
    assert agent_client.get("/api/knowledge-gaps/counts").json() == {"open": 1}
    # agents can't resolve gaps; admins (knowledge owners) can
    assert (
        agent_client.patch(
            f"/api/knowledge-gaps/{gap['id']}", json={"status": "resolved"}
        ).status_code
        == 403
    )
    admin = make_client()
    login(admin, make_user(Role.admin))
    r = admin.patch(
        f"/api/knowledge-gaps/{gap['id']}",
        json={"status": "resolved", "resolution_note": "Added router FAQ"},
    )
    assert r.json()["status"] == "resolved" and r.json()["resolved_by"] is not None
    assert agent_client.get("/api/knowledge-gaps").json() == []
    assert [
        g["id"]
        for g in agent_client.get("/api/knowledge-gaps", params={"status": "resolved"}).json()
    ] == [gap["id"]]
    kinds = [e["kind"] for e in agent_client.get(f"/api/tickets/{t.id}").json()["events"]]
    assert kinds[-2:] == ["knowledge_gap_created", "knowledge_gap_resolved"]


def test_manual_gap_without_draft(agent_client):
    r = agent_client.post("/api/knowledge-gaps", json={"question": "Do we ship to Antarctica?"})
    assert r.status_code == 201 and r.json()["draft_id"] is None
    assert agent_client.post("/api/knowledge-gaps", json={}).status_code == 422
