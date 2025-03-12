import pytest
from sqlalchemy import func, select

from app.db import SessionLocal
from app.models import Chunk, ChunkEmbedding, DocumentVersion, Role, VersionStatus
from app.services import ingestion
from app.services.embeddings import FakeEmbedder
from tests.factories import login, make_collection, make_group, make_user

V1 = b"# Refund Policy\n\nRefunds are available within 30 days.\n\n## Exceptions\n\nGift cards are final sale.\n"
V2 = b"# Refund Policy\n\nRefunds are available within 45 days.\n\n## Exceptions\n\nGift cards are final sale.\n\n## Shipping\n\nReturn shipping is free.\n"


@pytest.fixture(autouse=True)
def _bucket():
    from app.services import storage

    storage.ensure_bucket()


@pytest.fixture
def admin_client(client):
    login(client, make_user(Role.admin))
    return client


def upload(client, collection_id, content, name="refunds.md", **form):
    return client.post(
        f"/api/collections/{collection_id}/documents",
        files={"file": (name, content, "text/markdown")},
        data=form,
    )


def active_chunks(document_id):
    with SessionLocal() as db:
        return list(
            db.scalars(
                select(Chunk)
                .where(Chunk.document_id == document_id, Chunk.is_active)
                .order_by(Chunk.ordinal)
            )
        )


def test_upload_is_chunked_embedded_and_activated(admin_client):
    c = make_collection("Policies")
    r = upload(admin_client, c.id, V1)
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["created"] and body["queued"]
    doc_id = body["document"]["id"]
    detail = admin_client.get(f"/api/documents/{doc_id}").json()
    assert detail["title"] == "Refund Policy"
    v = detail["versions"][0]
    assert (v["status"], v["progress"], v["stage"], v["attempts"]) == ("ready", 100, "done", 1)
    assert v["embedding_model"] == FakeEmbedder.name
    chunks = active_chunks(doc_id)
    assert [ch.heading for ch in chunks] == ["Refund Policy", "Refund Policy > Exceptions"]
    with SessionLocal() as db:
        n = db.scalar(
            select(func.count())
            .select_from(ChunkEmbedding)
            .where(ChunkEmbedding.chunk_id.in_([ch.id for ch in chunks]))
        )
    assert n == 2
    assert admin_client.get(f"/api/collections/{c.id}").json()["document_count"] == 1


def test_new_version_retires_old_chunks(admin_client):
    c = make_collection("Policies")
    doc_id = upload(admin_client, c.id, V1).json()["document"]["id"]
    old_ids = {ch.id for ch in active_chunks(doc_id)}
    r = upload(admin_client, c.id, V2)  # same filename → new version of the same document
    assert r.json()["document"]["id"] == doc_id
    assert r.json()["version"]["version"] == 2
    versions = admin_client.get(f"/api/documents/{doc_id}").json()["versions"]
    assert [(v["version"], v["status"]) for v in versions] == [(2, "ready"), (1, "superseded")]
    live = active_chunks(doc_id)
    assert not old_ids & {ch.id for ch in live}
    assert any("45 days" in ch.text for ch in live)
    assert not any("30 days" in ch.text for ch in live)


def test_identical_reupload_is_deduplicated(admin_client):
    c = make_collection("Policies")
    first = upload(admin_client, c.id, V1).json()
    again = upload(admin_client, c.id, V1).json()
    assert again["created"] is False
    assert again["version"]["id"] == first["version"]["id"]


def test_reprocessing_is_idempotent(admin_client):
    c = make_collection("Policies")
    body = upload(admin_client, c.id, V1).json()
    doc_id, vid = body["document"]["id"], body["version"]["id"]
    before = [(ch.id, ch.ordinal, ch.text) for ch in active_chunks(doc_id)]
    r = admin_client.post(f"/api/documents/{doc_id}/versions/{vid}/reprocess")
    assert r.status_code == 200
    ingestion.process_version(vid)  # and once more directly, as a duplicate delivery would
    after = [(ch.id, ch.ordinal, ch.text) for ch in active_chunks(doc_id)]
    assert before == after  # same rows, same IDs: citations to them stay valid
    with SessionLocal() as db:
        assert (
            db.scalar(select(func.count()).select_from(Chunk).where(Chunk.version_id == vid)) == 2
        )


class FlakyEmbedder(FakeEmbedder):
    def __init__(self, failures):
        self.failures = failures

    def embed_documents(self, texts):
        if self.failures > 0:
            self.failures -= 1
            raise ConnectionError("embedding service unavailable")
        return super().embed_documents(texts)


def test_transient_failures_are_retried_with_backoff(admin_client, monkeypatch):
    flaky = FlakyEmbedder(failures=2)
    monkeypatch.setattr(ingestion, "get_embedder", lambda: flaky)
    delays = []
    monkeypatch.setattr(ingestion, "backoff_seconds", lambda n: delays.append(n) or 0)
    c = make_collection("Policies")
    body = upload(admin_client, c.id, V1).json()
    v = admin_client.get(f"/api/documents/{body['document']['id']}").json()["versions"][0]
    assert v["status"] == "ready"
    assert v["attempts"] == 3
    assert delays == [0, 1]


def test_gives_up_after_max_attempts_and_can_be_retried(admin_client, monkeypatch):
    monkeypatch.setattr(ingestion, "get_embedder", lambda: FlakyEmbedder(failures=99))
    monkeypatch.setattr(ingestion, "backoff_seconds", lambda n: 0)
    c = make_collection("Policies")
    body = upload(admin_client, c.id, V1).json()
    doc_id, vid = body["document"]["id"], body["version"]["id"]
    v = admin_client.get(f"/api/documents/{doc_id}").json()["versions"][0]
    assert v["status"] == "failed"
    assert v["attempts"] == ingestion.MAX_ATTEMPTS
    assert "gave up" in v["error"]
    monkeypatch.setattr(ingestion, "get_embedder", lambda: FakeEmbedder())
    assert admin_client.post(f"/api/documents/{doc_id}/versions/{vid}/reprocess").status_code == 200
    assert admin_client.get(f"/api/documents/{doc_id}").json()["versions"][0]["status"] == "ready"


def test_failed_new_version_keeps_previous_version_live(admin_client, monkeypatch):
    c = make_collection("Policies")
    doc_id = upload(admin_client, c.id, V1).json()["document"]["id"]
    monkeypatch.setattr(ingestion, "get_embedder", lambda: FlakyEmbedder(failures=99))
    monkeypatch.setattr(ingestion, "backoff_seconds", lambda n: 0)
    upload(admin_client, c.id, V2)
    detail = admin_client.get(f"/api/documents/{doc_id}").json()
    assert [(v["version"], v["status"]) for v in detail["versions"]] == [
        (2, "failed"),
        (1, "ready"),
    ]
    assert detail["current_version"]["version"] == 1
    assert any("30 days" in ch.text for ch in active_chunks(doc_id))


def test_empty_document_fails_permanently_without_retry(admin_client):
    c = make_collection("Policies")
    body = upload(admin_client, c.id, b"\n   \n").json()
    v = admin_client.get(f"/api/documents/{body['document']['id']}").json()["versions"][0]
    assert (v["status"], v["attempts"]) == ("failed", 1)
    assert "no text" in v["error"]


def test_out_of_order_processing_never_activates_older_version(admin_client, monkeypatch):
    c = make_collection("Policies")
    monkeypatch.setattr(ingestion, "enqueue", lambda vid: True)  # hold jobs, run them manually
    v1 = upload(admin_client, c.id, V1).json()
    v2 = upload(admin_client, c.id, V2).json()
    ingestion.process_version(v2["version"]["id"])
    ingestion.process_version(v1["version"]["id"])
    doc_id = v1["document"]["id"]
    with SessionLocal() as db:
        statuses = {
            v.version: v.status
            for v in db.scalars(
                select(DocumentVersion).where(DocumentVersion.document_id == doc_id)
            )
        }
    assert statuses == {1: VersionStatus.superseded, 2: VersionStatus.ready}
    assert any("45 days" in ch.text for ch in active_chunks(doc_id))


def test_delete_retires_chunks_immediately(admin_client):
    c = make_collection("Policies")
    doc_id = upload(admin_client, c.id, V1).json()["document"]["id"]
    assert admin_client.delete(f"/api/documents/{doc_id}").status_code == 204
    assert active_chunks(doc_id) == []
    assert admin_client.get(f"/api/documents/{doc_id}").status_code == 404
    assert admin_client.get(f"/api/collections/{c.id}/documents").json() == []
    # the filename is free again for a fresh document
    assert upload(admin_client, c.id, V1).json()["document"]["id"] != doc_id


@pytest.mark.parametrize(
    ("name", "content", "status"),
    [
        ("policy.pdf", b"%PDF-1.4", 422),
        ("policy.md", b"\xff\xfe\x00bad", 422),
        ("policy.md", b"", 422),
        ("big.md", b"a" * (ingestion.MAX_UPLOAD_BYTES + 1), 413),
    ],
)
def test_upload_validation(admin_client, name, content, status):
    c = make_collection("Policies")
    assert upload(admin_client, c.id, content, name=name).status_code == status


def test_agents_read_but_cannot_upload(client, make_client):
    agent = make_user()
    team = make_group("Team", agent)
    readable = make_collection("Readable", groups=(team,))
    hidden = make_collection("Hidden")
    admin_client = make_client()
    login(admin_client, make_user(Role.admin))
    doc = upload(admin_client, readable.id, V1).json()["document"]
    hidden_doc = upload(admin_client, hidden.id, V1).json()["document"]

    login(client, agent)
    assert [d["id"] for d in client.get(f"/api/collections/{readable.id}/documents").json()] == [
        doc["id"]
    ]
    assert upload(client, readable.id, V2).status_code == 403
    assert client.get(f"/api/collections/{hidden.id}/documents").status_code == 404
    assert client.get(f"/api/documents/{hidden_doc['id']}").status_code == 404
    url = client.get(
        f"/api/documents/{doc['id']}/versions/{doc['current_version']['id']}/download"
    ).json()["url"]
    assert "X-Amz-Expires=300" in url
