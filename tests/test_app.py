from fastapi.testclient import TestClient

from app.main import create_app


def test_health_and_openapi() -> None:
    client = TestClient(create_app())
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"code": 200, "message": "success", "data": {"status": "ok"}}
    assert client.get("/docs").status_code == 200
    assert "/health" in client.get("/openapi.json").json()["paths"]
