"""Authorization is part of retrieval, not a post-processing step."""

import random

import pytest

from app.db import SessionLocal
from app.models import Role, User
from app.services.permissions import readable_collection_ids
from app.services.retrieval import retrieve
from tests.factories import add_document, login, make_collection, make_group, make_user

PUBLIC = "# Refund Policy\n\nCustomers can request a refund within 30 days of purchase.\n"
SECRET = (
    "# Incident Runbook\n\nThe break-glass database password rotation happens every Friday. "
    "Refund fraud investigations use the internal case tracker ZEBRA-7.\n"
)


def search(user, q, **kw):
    with SessionLocal() as db:
        return retrieve(db, db.get(User, user.id), q, **kw)


@pytest.fixture
def world():
    agent, outsider = make_user(name="Agent"), make_user(name="Outsider")
    support = make_group("Support", agent)
    public = make_collection("Public", groups=(support,))
    secret = make_collection("Security")
    add_document(public, "refunds.md", PUBLIC)
    add_document(secret, "runbook.md", SECRET)
    return {
        "agent": agent,
        "outsider": outsider,
        "support": support,
        "public": public,
        "secret": secret,
    }


def test_agent_only_retrieves_readable_collections(world):
    # The query matches the secret document best, lexically and semantically.
    r = search(world["agent"], "break-glass database password rotation ZEBRA-7 refund")
    assert r.chunks, "should still find the readable refund policy"
    assert {c.collection_name for c in r.chunks} == {"Public"}
    assert not any("ZEBRA-7" in c.text for c in r.chunks)


def test_filter_runs_before_limit_not_after(world):
    # If permissions were applied after ranking, k=1 would return the (better matching) secret
    # chunk and then filter it away, leaving nothing.
    r = search(world["agent"], "break-glass database password rotation ZEBRA-7 refund", k=1)
    assert [c.collection_name for c in r.chunks] == ["Public"]


def test_user_without_any_grant_gets_nothing(world):
    r = search(world["outsider"], "refund within 30 days")
    assert r.chunks == []
    assert not r.has_evidence


def test_admin_reads_everything(world):
    admin = make_user(Role.admin)
    r = search(admin, "ZEBRA-7 case tracker")
    assert r.chunks[0].collection_name == "Security"


def test_revoking_access_applies_to_the_next_query(world, client):
    admin = make_user(Role.admin)
    login(client, admin)
    assert search(world["agent"], "refund within 30 days").chunks
    grant_id = client.get(f"/api/collections/{world['public'].id}/grants").json()[0]["id"]
    client.delete(f"/api/collections/{world['public'].id}/grants/{grant_id}")
    assert search(world["agent"], "refund within 30 days").chunks == []


def test_removing_group_membership_applies_immediately(world, client):
    login(client, make_user(Role.admin))
    client.delete(f"/api/groups/{world['support'].id}/members/{world['agent'].id}")
    assert search(world["agent"], "refund within 30 days").chunks == []


def test_deleted_document_is_never_retrieved(world, client):
    login(client, make_user(Role.admin))
    doc_id = search(world["agent"], "refund").chunks[0].document_id
    client.delete(f"/api/documents/{doc_id}")
    assert search(world["agent"], "refund within 30 days").chunks == []


def test_only_current_version_is_retrieved(world):
    add_document(
        world["public"],
        "refunds.md",
        "# Refund Policy\n\nCustomers can request a refund within 60 days of purchase.\n",
    )
    r = search(world["agent"], "how many days to request a refund")
    texts = " ".join(c.text for c in r.chunks)
    assert "60 days" in texts and "30 days" not in texts
    assert {c.version for c in r.chunks} == {2}


def test_scoping_to_collections_cannot_widen_access(world):
    r = search(world["agent"], "ZEBRA-7", collection_ids=[world["secret"].id])
    assert r.chunks == []


def test_lexical_match_finds_exact_identifiers(world):
    admin = make_user(Role.admin)
    r = search(admin, "ZEBRA-7")
    assert r.chunks[0].keyword_rank == 1


def test_randomized_grants_never_leak():
    """Many users, collections and random grants: every hit must be in the user's readable set,
    computed independently of the retrieval code."""
    rng = random.Random(42)
    users = [make_user() for _ in range(6)]
    groups = [make_group(f"G{i}", *rng.sample(users, 2)) for i in range(3)]
    collections = []
    for i in range(6):
        grant_users = tuple(rng.sample(users, rng.randint(0, 2)))
        grant_groups = tuple(rng.sample(groups, rng.randint(0, 1)))
        c = make_collection(f"C{i}", users=grant_users, groups=grant_groups)
        add_document(
            c,
            f"doc{i}.md",
            f"# Policy {i}\n\nShared refund wording plus marker M{i} for collection {i}.\n",
        )
        collections.append(c)
    for u in users:
        with SessionLocal() as db:
            user = db.get(User, u.id)
            allowed = set(db.scalars(readable_collection_ids(user)))
            expected_ids = {c.id for c in collections if c.id in allowed}
            hits = retrieve(db, user, "shared refund wording marker", k=20).chunks
            assert {h.collection_id for h in hits} == expected_ids
            for h in hits:
                assert h.collection_id in allowed


def test_search_api_requires_auth_and_filters(world, client):
    assert client.get("/api/search", params={"q": "refund"}).status_code == 401
    login(client, world["agent"])
    body = client.get("/api/search", params={"q": "ZEBRA-7 refund"}).json()
    assert {h["collection_name"] for h in body["hits"]} == {"Public"}
