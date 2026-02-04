"""Test configuration. Fakes are forced for every provider: tests never touch the network."""

import os

os.environ.update(
    ENV="test",
    EMBEDDING_PROVIDER="fake",
    LLM_PROVIDER="fake",
    CELERY_EAGER="true",
    DATABASE_URL=os.environ.get(
        "TEST_DATABASE_URL",
        "postgresql+psycopg://supportlens:supportlens@localhost:5433/supportlens_test",
    ),
    S3_BUCKET=os.environ.get("TEST_S3_BUCKET", "supportlens-test"),
    REDIS_URL=os.environ.get("TEST_REDIS_URL", "redis://localhost:6379/15"),
)
for key, value in {
    "S3_ENDPOINT_URL": "http://localhost:9000",
    "S3_ACCESS_KEY": "supportlens",
    "S3_SECRET_KEY": "supportlens-secret",
}.items():
    os.environ.setdefault(key, value)
