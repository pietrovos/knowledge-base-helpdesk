from app.models import Role
from tests.factories import PASSWORD, login, make_user


def test_login_sets_httponly_cookie_and_me_works(client):
    user = make_user()
    r = client.post("/api/auth/login", json={"email": user.email.upper(), "password": PASSWORD})
    assert r.status_code == 200
    cookie = r.headers["set-cookie"]
    assert "HttpOnly" in cookie and "SameSite=lax" in cookie
    assert client.get("/api/auth/me").json()["email"] == user.email


def test_bad_password_and_unknown_email_get_same_error(client):
    user = make_user()
    a = client.post("/api/auth/login", json={"email": user.email, "password": "wrong-password"})
    b = client.post("/api/auth/login", json={"email": "nobody@example.com", "password": "x"})
    assert a.status_code == b.status_code == 401
    assert a.json() == b.json()


def test_unauthenticated_requests_are_rejected(client):
    assert client.get("/api/auth/me").status_code == 401
    assert client.get("/api/collections").status_code == 401


def test_logout_clears_session(client):
    login(client, make_user())
    assert client.post("/api/auth/logout").status_code == 204
    assert client.get("/api/auth/me").status_code == 401


def test_deactivated_user_is_locked_out_immediately(client, make_client):
    admin, agent = make_user(Role.admin), make_user()
    agent_client = make_client()
    login(agent_client, agent)
    login(client, admin)
    assert agent_client.get("/api/auth/me").status_code == 200
    client.patch(f"/api/users/{agent.id}", json={"is_active": False})
    assert agent_client.get("/api/auth/me").status_code == 401


def test_state_changing_requests_need_csrf_header(make_client):
    from fastapi.testclient import TestClient

    from app.main import app

    with TestClient(app) as bare:
        r = bare.post("/api/auth/login", json={"email": "a@b.co", "password": "x"})
    assert r.status_code == 403
    assert r.json()["detail"] == "Missing CSRF header"


def test_tampered_token_is_rejected(client):
    login(client, make_user())
    token = client.cookies.get("sl_session")
    client.cookies.set("sl_session", token[:-2] + ("AA" if not token.endswith("AA") else "BB"))
    assert client.get("/api/auth/me").status_code == 401
