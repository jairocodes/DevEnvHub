from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from api.core.config import settings
from api.db.session import Base, get_db
from api.main import app
from api.routers import environments as environments_router

engine = create_engine(
    "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
)
TestingSessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
Base.metadata.create_all(engine)


def _override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = _override_get_db

client = TestClient(app)


def _register_and_login(email: str) -> dict:
    client.post("/auth/register", json={"email": email, "password": "secret123"})
    login = client.post("/auth/login", json={"email": email, "password": "secret123"})
    return {"Authorization": f"Bearer {login.json()['access_token']}"}


def test_non_admin_cannot_list_users() -> None:
    headers = _register_and_login("regular-user@example.com")
    response = client.get("/admin/users", headers=headers)
    assert response.status_code == 403


def test_allowlisted_email_is_promoted_on_login(monkeypatch) -> None:
    monkeypatch.setattr(settings, "admin_emails", "admin-promo@example.com")
    headers = _register_and_login("admin-promo@example.com")

    response = client.get("/admin/users", headers=headers)
    assert response.status_code == 200
    me = next(u for u in response.json() if u["email"] == "admin-promo@example.com")
    assert me["is_admin"] is True


def test_admin_can_update_and_reset_user_quota(monkeypatch) -> None:
    monkeypatch.setattr(settings, "admin_emails", "admin-quota@example.com")
    admin_headers = _register_and_login("admin-quota@example.com")
    _register_and_login("target-user@example.com")

    users = client.get("/admin/users", headers=admin_headers).json()
    target = next(u for u in users if u["email"] == "target-user@example.com")

    update_response = client.patch(
        f"/admin/users/{target['id']}/quota",
        json={"max_environments": 1, "cpu_limit": 0.25},
        headers=admin_headers,
    )
    assert update_response.status_code == 200
    updated = update_response.json()
    assert updated["max_environments"] == 1
    assert updated["cpu_limit"] == 0.25
    assert updated["mem_limit_mb"] is None  # untouched, not sent in the payload

    reset_response = client.patch(
        f"/admin/users/{target['id']}/quota",
        json={"max_environments": None},
        headers=admin_headers,
    )
    assert reset_response.status_code == 200
    assert reset_response.json()["max_environments"] is None
    assert reset_response.json()["cpu_limit"] == 0.25  # still untouched


def test_non_admin_cannot_update_quota() -> None:
    headers = _register_and_login("not-an-admin@example.com")
    response = client.patch(
        "/admin/users/1/quota", json={"max_environments": 1}, headers=headers
    )
    assert response.status_code == 403


def test_admin_quota_override_is_enforced(monkeypatch) -> None:
    monkeypatch.setattr(settings, "admin_emails", "admin-enforce@example.com")
    monkeypatch.setattr(
        environments_router.compose_service,
        "prepare_workspace",
        lambda *args, **kwargs: Path("fake-compose.yml"),
    )
    monkeypatch.setattr(environments_router.compose_service, "up", lambda *args, **kwargs: None)

    admin_headers = _register_and_login("admin-enforce@example.com")
    limited_headers = _register_and_login("limited-user@example.com")

    users = client.get("/admin/users", headers=admin_headers).json()
    limited = next(u for u in users if u["email"] == "limited-user@example.com")
    client.patch(
        f"/admin/users/{limited['id']}/quota",
        json={"max_environments": 1},
        headers=admin_headers,
    )

    first = client.post(
        "/environments", json={"name": "one", "template": "node"}, headers=limited_headers
    )
    assert first.status_code == 201

    second = client.post(
        "/environments", json={"name": "two", "template": "node"}, headers=limited_headers
    )
    assert second.status_code == 429
