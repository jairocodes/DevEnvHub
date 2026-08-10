from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

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


def test_create_list_delete_environment(monkeypatch) -> None:
    monkeypatch.setattr(
        environments_router.compose_service,
        "prepare_workspace",
        lambda *args, **kwargs: Path("fake-compose.yml"),
    )
    monkeypatch.setattr(environments_router.compose_service, "up", lambda *args, **kwargs: None)
    monkeypatch.setattr(environments_router.compose_service, "down", lambda *args, **kwargs: None)

    create_response = client.post("/environments", json={"name": "demo", "template": "node"})
    assert create_response.status_code == 201
    body = create_response.json()
    assert body["status"] == "running"
    assert body["template"] == "node"

    list_response = client.get("/environments")
    assert list_response.status_code == 200
    assert any(env["name"] == "demo" for env in list_response.json())

    delete_response = client.delete(f"/environments/{body['id']}")
    assert delete_response.status_code == 204


def test_create_environment_unknown_template() -> None:
    response = client.post("/environments", json={"name": "x", "template": "does-not-exist"})
    assert response.status_code == 404
