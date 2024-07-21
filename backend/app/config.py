from functools import lru_cache
from typing import Literal

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


DEV_JWT_SECRET = "dev-only-insecure-secret-change-me-in-prod"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    env: Literal["dev", "test", "prod"] = "dev"
    database_url: str = "postgresql+psycopg://supportlens:supportlens@localhost:5433/supportlens"
    redis_url: str = "redis://localhost:6379/0"

    # Object storage (S3 / MinIO). The public endpoint is what browsers can reach for presigned URLs.
    s3_endpoint_url: str | None = "http://localhost:9000"
    s3_public_endpoint_url: str | None = None
    s3_bucket: str = "supportlens-docs"
    s3_region: str = "us-east-1"
    s3_access_key: str | None = "supportlens"
    s3_secret_key: str | None = "supportlens-secret"

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
    llm_timeout_seconds: float = 45.0
    # Fake provider behaviour, used by tests and the "provider down" demo.
    fake_llm_mode: Literal["ok", "error", "timeout", "slow"] = "ok"

    celery_eager: bool = False

    @model_validator(mode="after")
    def _prod_requires_real_secret(self) -> "Settings":
        if self.env == "prod" and (self.jwt_secret == DEV_JWT_SECRET or len(self.jwt_secret) < 32):
            raise ValueError("JWT_SECRET must be set to a random value of 32+ characters in prod")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
