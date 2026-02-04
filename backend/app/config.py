from functools import lru_cache
from typing import Literal

from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

DEV_JWT_SECRET = "dev-only-insecure-secret-change-me-in-prod"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    env: Literal["dev", "test", "prod"] = "dev"
    database_url: str = "postgresql+psycopg://supportlens:supportlens@localhost:5433/supportlens"
    # Alternative to DATABASE_URL for platforms that inject the password as its own secret
    # (RDS-managed master password via ECS secrets).
    db_host: str | None = None
    db_port: int = 5432
    db_name: str = "supportlens"
    db_user: str | None = None
    db_password: str | None = None
    redis_url: str = "redis://localhost:6379/0"

    # Object storage (S3 / MinIO). The public endpoint is what browsers can reach for presigned URLs.
    # Unset in AWS: the default S3 endpoint and the IAM task role are used.
    s3_endpoint_url: str | None = None
    s3_public_endpoint_url: str | None = None
    s3_bucket: str = "supportlens-docs"
    s3_region: str = "us-east-1"
    s3_access_key: str | None = None
    s3_secret_key: str | None = None

    # Auth
    jwt_secret: str = DEV_JWT_SECRET
    jwt_ttl_minutes: int = 60 * 12
    cookie_secure: bool = False

    # Providers
    embedding_provider: Literal["local", "voyage", "fake"] = "local"
    local_embedding_model: str = "BAAI/bge-small-en-v1.5"
    voyage_model: str = "voyage-3.5-lite"
    voyage_api_key: str | None = None

    llm_provider: Literal["anthropic", "fake"] = "fake"
    llm_model: str = "claude-opus-5-5"
    anthropic_api_key: str | None = None
    llm_effort: Literal["low", "medium", "high", "xhigh", "max"] = "medium"
    llm_timeout_seconds: float = 45.0
    # Fake provider behaviour, used by tests and the "provider down" demo.
    fake_llm_mode: Literal["ok", "error", "timeout", "slow", "bad_citations", "uncited"] = "ok"

    celery_eager: bool = False

    @field_validator(
        "s3_endpoint_url",
        "s3_public_endpoint_url",
        "s3_access_key",
        "s3_secret_key",
        "anthropic_api_key",
        "voyage_api_key",
        mode="before",
    )
    @classmethod
    def _blank_is_none(cls, v):
        # In AWS these are unset (S3 default endpoint, IAM task role); compose passes "".
        return v or None

    @model_validator(mode="after")
    def _database_from_parts(self) -> "Settings":
        if self.db_host and self.db_user and self.db_password:
            from sqlalchemy.engine import URL

            self.database_url = URL.create(
                "postgresql+psycopg",
                username=self.db_user,
                password=self.db_password,
                host=self.db_host,
                port=self.db_port,
                database=self.db_name,
                query={"sslmode": "require"},
            ).render_as_string(hide_password=False)
        return self

    @model_validator(mode="after")
    def _prod_requires_real_secret(self) -> "Settings":
        if self.env == "prod" and (self.jwt_secret == DEV_JWT_SECRET or len(self.jwt_secret) < 32):
            raise ValueError("JWT_SECRET must be set to a random value of 32+ characters in prod")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
