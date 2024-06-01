from sqlalchemy import text

from app.db import engine


def test_health(client):
    r = client.get("/api/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


def test_baseline_migration_enables_pgvector():
    with engine.connect() as conn:
        exts = set(conn.execute(text("SELECT extname FROM pg_extension")).scalars())
    assert {"vector", "citext"} <= exts


def test_storage_roundtrip():
    from app.services import storage

    storage.ensure_bucket()
    storage.put_object("tests/hello.txt", b"hello", "text/plain")
    assert storage.get_object("tests/hello.txt") == b"hello"
    url = storage.presigned_get("tests/hello.txt", "hello.txt")
    assert "X-Amz-Signature" in url
