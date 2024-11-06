from tests.factories import login, make_ticket, make_user


def test_create_and_view_ticket(client):
    login(client, make_user())
    r = client.post("/api/tickets", json={"subject": "Cannot log in", "customer_name": "Pat",
                                          "customer_email": "pat@example.com", "body": "Password reset email never arrives."})
    assert r.status_code == 201
    t = client.get(f"/api/tickets/{r.json()['id']}").json()
    assert t["status"] == "open"
    assert [m["author_type"] for m in t["messages"]] == ["customer"]
    assert t["events"][0]["kind"] == "created"


def test_inbox_views_and_ordering(client):
    me, other = make_user(), make_user()
    low = make_ticket("Low", priority="low")
    urgent = make_ticket("Urgent", priority="urgent")
    mine = make_ticket("Mine", assignee=me)
    theirs = make_ticket("Theirs", assignee=other)
    pending = make_ticket("Pending", status="pending")
    resolved = make_ticket("Resolved", status="resolved")
    login(client, me)

    def ids(view, **params):
        return [t["id"] for t in client.get("/api/tickets", params={"view": view, **params}).json()["items"]]

    active = ids("active")
    assert active[0] == urgent.id and resolved.id not in active
    assert set(active) == {low.id, urgent.id, mine.id, theirs.id, pending.id}
    assert ids("mine") == [mine.id]
    assert set(ids("unassigned")) == {low.id, urgent.id, pending.id}
    assert ids("resolved") == [resolved.id]
    assert ids("all", q="theirs") == [theirs.id]
    counts = client.get("/api/tickets/counts").json()
    assert counts == {"active": 5, "mine": 1, "unassigned": 3, "pending": 1, "escalated": 0}
    page = client.get("/api/tickets", params={"view": "active", "page_size": 2, "page": 2}).json()
    assert page["total"] == 5 and len(page["items"]) == 2
    assert page["items"][0]["preview"].startswith("I returned")


def test_status_priority_and_assignment_are_audited(client):
    agent, teammate = make_user(name="Alex"), make_user(name="Sam")
    t = make_ticket()
    login(client, agent)
    r = client.patch(f"/api/tickets/{t.id}", json={"status": "pending", "priority": "high",
                                                   "assignee_id": teammate.id})
    body = r.json()
    assert (body["status"], body["priority"], body["assignee"]["name"]) == ("pending", "high", "Sam")
    kinds = [(e["kind"], e["actor"]["name"]) for e in body["events"]]
    assert kinds == [("status_changed", "Alex"), ("priority_changed", "Alex"), ("assigned", "Alex")]
    assert client.patch(f"/api/tickets/{t.id}", json={"unassign": True}).json()["assignee"] is None


def test_escalation_requires_reason(client):
    login(client, make_user())
    t = make_ticket()
    assert client.patch(f"/api/tickets/{t.id}", json={"status": "escalated"}).status_code == 422
    r = client.patch(f"/api/tickets/{t.id}", json={"status": "escalated", "escalation_reason": "Legal threat"})
    assert r.json()["escalation_reason"] == "Legal threat"
    assert r.json()["events"][-1]["data"] == {"from": "open", "to": "escalated", "reason": "Legal threat"}
    # leaving the escalated state clears the reason
    assert client.patch(f"/api/tickets/{t.id}", json={"status": "open"}).json()["escalation_reason"] is None


def test_reply_assigns_unowned_ticket_and_can_set_status(client):
    agent = make_user(name="Alex")
    t = make_ticket()
    login(client, agent)
    r = client.post(f"/api/tickets/{t.id}/messages", json={"body": "We're on it.", "status": "pending"})
    assert r.status_code == 201
    detail = client.get(f"/api/tickets/{t.id}").json()
    assert detail["assignee"]["name"] == "Alex"
    assert detail["status"] == "pending"
    assert [m["author_type"] for m in detail["messages"]] == ["customer", "agent"]


def test_internal_note_does_not_assign(client):
    login(client, make_user())
    t = make_ticket()
    client.post(f"/api/tickets/{t.id}/messages", json={"body": "Checking with billing", "is_internal": True})
    assert client.get(f"/api/tickets/{t.id}").json()["assignee"] is None


def test_cannot_assign_inactive_user(client):
    login(client, make_user())
    gone = make_user(active=False)
    t = make_ticket()
    assert client.patch(f"/api/tickets/{t.id}", json={"assignee_id": gone.id}).status_code == 422


def test_missing_ticket_404(client):
    login(client, make_user())
    assert client.get("/api/tickets/999999").status_code == 404
