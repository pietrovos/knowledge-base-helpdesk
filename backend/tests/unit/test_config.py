import pytest

from app.config import Settings


def test_database_url_from_parts_escapes_password():
    s = Settings(db_host="db.example.com", db_user="app", db_password="p@ss/w:rd", db_name="sl")
    assert (
        s.database_url
        == "postgresql+psycopg://app:p%40ss%2Fw%3Ard@db.example.com:5432/sl?sslmode=require"
    )


def test_prod_rejects_default_jwt_secret():
    with pytest.raises(ValueError):
        Settings(env="prod")
    assert Settings(env="prod", jwt_secret="x" * 40).env == "prod"


def test_blank_optional_settings_become_none():
    assert Settings(s3_endpoint_url="", anthropic_api_key="").s3_endpoint_url is None
