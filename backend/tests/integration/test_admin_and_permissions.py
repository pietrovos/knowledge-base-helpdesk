from app.db import SessionLocal
from app.models import Role
from app.services.permissions import can_read_collection
from tests.factories import login, make_collection, make_group, make_user


def test_agents_cannot_use_admin_endpoints(client):
    login(client, make_user(Role.agent))
    assert client.get("/api/users").status_code == 403
    assert client.post("/api/collections", json={"name": "x"}).status_code == 403
    assert client.post("/api/groups", json={"name": "x"}).status_code == 403


def test_admin_manages_users_groups_collections_and_grants(client):
    login(client, make_user(Role.admin))
    u = client.post(
        "/api/users",
        json={"email": "new@example.com", "name": "New Agent", "password": "longenough1"},
    ).json()
    assert u["role"] == "agent"
    assert (
        client.post(
            "/api/users",
            json={"email": "NEW@example.com", "name": "Dup", "password": "longenough1"},
        ).status_code
        == 409
    )
    g = client.post("/api/groups", json={"name": "Tier 2"}).json()
    g = client.post(f"/api/groups/{g['id']}/members", json={"user_id": u["id"]}).json()
    assert [m["id"] for m in g["members"]] == [u["id"]]
    c = client.post(
        "/api/collections", json={"name": "Billing", "description": "Billing policies"}
    ).json()
    grant = client.post(f"/api/collections/{c['id']}/grants", json={"group_id": g["id"]})
    assert grant.status_code == 201
    assert grant.json()["group"]["name"] == "Tier 2"
    dup = client.post(f"/api/collections/{c['id']}/grants", json={"group_id": g["id"]})
    assert dup.status_code == 409
    bad = client.post(
        f"/api/collections/{c['id']}/grants", json={"group_id": g["id"], "user_id": u["id"]}
    )
    assert bad.status_code == 422


def test_admin_cannot_demote_self(client):
    admin = make_user(Role.admin)
    login(client, admin)
    assert client.patch(f"/api/users/{admin.id}", json={"role": "agent"}).status_code == 400


def test_collection_visibility_follows_direct_and_group_grants(client):
    alice, bob, carol = make_user(), make_user(), make_user()
    support = make_group("Support", bob)
    direct = make_collection("Direct", users=(alice,))
    via_group = make_collection("Via group", groups=(support,))
    hidden = make_collection("Hidden")

    login(client, alice)
    assert [c["name"] for c in client.get("/api/collections").json()] == ["Direct"]
    assert client.get(f"/api/collections/{via_group.id}").status_code == 404
    assert client.get(f"/api/collections/{hidden.id}").status_code == 404

    login(client, bob)
    assert [c["name"] for c in client.get("/api/collections").json()] == ["Via group"]

    login(client, carol)
    assert client.get("/api/collections").json() == []
    assert client.get(f"/api/collections/{direct.id}").status_code == 404


def test_revoking_grant_or_membership_takes_effect_immediately(client, make_client):
    admin, agent = make_user(Role.admin), make_user()
    team = make_group("Team", agent)
    c = make_collection("Policies", groups=(team,))
    agent_client = make_client()
    login(agent_client, agent)
    login(client, admin)
    assert agent_client.get(f"/api/collections/{c.id}").status_code == 200

    client.delete(f"/api/groups/{team.id}/members/{agent.id}")
    assert agent_client.get(f"/api/collections/{c.id}").status_code == 404

    client.post(f"/api/groups/{team.id}/members", json={"user_id": agent.id})
    assert agent_client.get(f"/api/collections/{c.id}").status_code == 200
    grant_id = client.get(f"/api/collections/{c.id}/grants").json()[0]["id"]
    assert client.delete(f"/api/collections/{c.id}/grants/{grant_id}").status_code == 204
    assert agent_client.get(f"/api/collections/{c.id}").status_code == 404


def test_admins_can_read_every_collection():
    admin = make_user(Role.admin)
    c = make_collection("Secret")
    with SessionLocal() as db:
        assert can_read_collection(db, admin, c.id)
