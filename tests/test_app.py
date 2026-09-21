from pathlib import Path

from fastapi.testclient import TestClient

from app.core.config import Settings
from app.main import create_app


def test_health_and_openapi(tmp_path: Path) -> None:
    client = TestClient(create_app(Settings(data_dir=tmp_path, seed_demo_books=False)))
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {
        "code": 200,
        "message": "操作成功",
        "data": {"status": "正常"},
    }
    assert client.get("/docs").status_code == 200
    assert "/health" in client.get("/openapi.json").json()["paths"]


def test_validation_and_http_errors_are_chinese(tmp_path: Path) -> None:
    client = TestClient(create_app(Settings(data_dir=tmp_path, seed_demo_books=False)))

    missing = client.post("/api/members", json={})
    assert missing.status_code == 422
    assert missing.json()["error"] == {
        "code": "VALIDATION_ERROR",
        "message": "该字段为必填项",
        "field": "name",
    }

    invalid_date = client.post(
        "/api/books/1/bill-previews",
        json={"period": {"start": "2026-09-01", "end": "2026-09-31"}},
    )
    assert invalid_date.status_code == 422
    assert invalid_date.json()["error"] == {
        "code": "VALIDATION_ERROR",
        "message": "请输入有效日期，日期必须真实存在且格式为 YYYY-MM-DD",
        "field": "period.end",
    }

    missing_route = client.get("/api/does-not-exist")
    assert missing_route.status_code == 404
    assert missing_route.json()["error"]["message"] == "请求的接口不存在"
