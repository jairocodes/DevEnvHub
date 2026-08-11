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


def _auth_headers(email: str) -> dict:
    client.post("/auth/register", json={"email": email, "password": "secret123"})
    login = client.post("/auth/login", json={"email": email, "password": "secret123"})
    token = login.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def test_create_list_delete_environment(monkeypatch) -> None:
    monkeypatch.setattr(
        environments_router.compose_service,
        "prepare_workspace",
        lambda *args, **kwargs: Path("fake-compose.yml"),
    )
    monkeypatch.setattr(environments_router.compose_service, "up", lambda *args, **kwargs: None)
    monkeypatch.setattr(environments_router.compose_service, "down", lambda *args, **kwargs: None)

    headers = _auth_headers("env-owner@example.com")

    create_response = client.post(
        "/environments", json={"name": "demo", "template": "node"}, headers=headers
    )
    assert create_response.status_code == 201
    body = create_response.json()
    assert body["status"] == "running"
    assert body["template"] == "node"

    list_response = client.get("/environments", headers=headers)
    assert list_response.status_code == 200
    assert any(env["name"] == "demo" for env in list_response.json())

    delete_response = client.delete(f"/environments/{body['id']}", headers=headers)
    assert delete_response.status_code == 204


def test_create_environment_with_django_template(monkeypatch) -> None:
    monkeypatch.setattr(
        environments_router.compose_service,
        "prepare_workspace",
        lambda *args, **kwargs: Path("fake-compose.yml"),
    )
    monkeypatch.setattr(environments_router.compose_service, "up", lambda *args, **kwargs: None)

    headers = _auth_headers("django-env@example.com")
    response = client.post(
        "/environments", json={"name": "django-demo", "template": "django"}, headers=headers
    )
    assert response.status_code == 201
    assert response.json()["port"] == 8000


def test_create_environment_with_laravel_template(monkeypatch) -> None:
    monkeypatch.setattr(
        environments_router.compose_service,
        "prepare_workspace",
        lambda *args, **kwargs: Path("fake-compose.yml"),
    )
    monkeypatch.setattr(environments_router.compose_service, "up", lambda *args, **kwargs: None)

    headers = _auth_headers("laravel-env@example.com")
    response = client.post(
        "/environments", json={"name": "laravel-demo", "template": "laravel"}, headers=headers
    )
    assert response.status_code == 201
    assert response.json()["port"] == 8080


def test_create_environment_with_spring_template(monkeypatch) -> None:
    monkeypatch.setattr(
        environments_router.compose_service,
        "prepare_workspace",
        lambda *args, **kwargs: Path("fake-compose.yml"),
    )
    monkeypatch.setattr(environments_router.compose_service, "up", lambda *args, **kwargs: None)

    headers = _auth_headers("spring-env@example.com")
    response = client.post(
        "/environments", json={"name": "spring-demo", "template": "spring"}, headers=headers
    )
    assert response.status_code == 201
    assert response.json()["port"] == 8081


def test_environment_quota_enforced(monkeypatch) -> None:
    monkeypatch.setattr(
        environments_router.compose_service,
        "prepare_workspace",
        lambda *args, **kwargs: Path("fake-compose.yml"),
    )
    monkeypatch.setattr(environments_router.compose_service, "up", lambda *args, **kwargs: None)

    headers = _auth_headers("quota-test@example.com")
    for i in range(settings.default_max_environments):
        response = client.post(
            "/environments", json={"name": f"quota-env-{i}", "template": "node"}, headers=headers
        )
        assert response.status_code == 201

    over_quota_response = client.post(
        "/environments", json={"name": "one-too-many", "template": "node"}, headers=headers
    )
    assert over_quota_response.status_code == 429


def test_create_environment_unknown_template() -> None:
    headers = _auth_headers("env-unknown-template@example.com")
    response = client.post(
        "/environments", json={"name": "x", "template": "does-not-exist"}, headers=headers
    )
    assert response.status_code == 404


def test_environments_are_scoped_per_user(monkeypatch) -> None:
    monkeypatch.setattr(
        environments_router.compose_service,
        "prepare_workspace",
        lambda *args, **kwargs: Path("fake-compose.yml"),
    )
    monkeypatch.setattr(environments_router.compose_service, "up", lambda *args, **kwargs: None)

    owner_headers = _auth_headers("owner@example.com")
    other_headers = _auth_headers("other@example.com")

    client.post("/environments", json={"name": "owned", "template": "node"}, headers=owner_headers)

    other_list = client.get("/environments", headers=other_headers)
    assert other_list.status_code == 200
    assert all(env["name"] != "owned" for env in other_list.json())
