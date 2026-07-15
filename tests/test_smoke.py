from fastapi.testclient import TestClient

from app.main import app


def test_dashboard_smoke() -> None:
    client = TestClient(app)

    response = client.get("/")

    assert response.status_code == 200
    assert response.json()["status"] == "Pokemon Cube Finder is ready for implementation"
