from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from api.db.session import Base, get_db
from api.main import app

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


def test_register_and_login() -> None:
    register_response = client.post(
        "/auth/register", json={"email": "auth-test@example.com", "password": "secret123"}
    )
    assert register_response.status_code == 201

    login_response = client.post(
        "/auth/login", json={"email": "auth-test@example.com", "password": "secret123"}
    )
    assert login_response.status_code == 200
    assert login_response.json()["token_type"] == "bearer"


def test_register_duplicate_email_rejected() -> None:
    client.post("/auth/register", json={"email": "dup@example.com", "password": "secret123"})
    response = client.post(
        "/auth/register", json={"email": "dup@example.com", "password": "other-pass"}
    )
    assert response.status_code == 409


def test_login_wrong_password_rejected() -> None:
    client.post("/auth/register", json={"email": "wrongpw@example.com", "password": "secret123"})
    response = client.post(
        "/auth/login", json={"email": "wrongpw@example.com", "password": "not-the-password"}
    )
    assert response.status_code == 401


def test_environments_requires_auth() -> None:
    response = client.get("/environments")
    assert response.status_code == 401
