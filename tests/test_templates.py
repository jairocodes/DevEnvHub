from fastapi.testclient import TestClient

from api.main import app

client = TestClient(app)


def test_list_templates_includes_node() -> None:
    response = client.get("/templates")
    assert response.status_code == 200
    names = [t["name"] for t in response.json()]
    assert "node" in names


def test_list_templates_includes_django() -> None:
    response = client.get("/templates")
    assert response.status_code == 200
    names = [t["name"] for t in response.json()]
    assert "django" in names


def test_list_templates_includes_laravel() -> None:
    response = client.get("/templates")
    assert response.status_code == 200
    names = [t["name"] for t in response.json()]
    assert "laravel" in names
