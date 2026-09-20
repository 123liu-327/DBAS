from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from fastapi.testclient import TestClient

from app.core.config import Settings
from app.main import create_app
from app.storage import FileStore


def make_client(tmp_path: Path) -> TestClient:
    return TestClient(create_app(Settings(data_dir=tmp_path, seed_demo_books=False)))


def create_book(client: TestClient, name: str = "3栋402") -> dict:
    response = client.post("/api/books", json={"name": name})
    assert response.status_code == 201
    return response.json()["data"]


def create_member(client: TestClient, name: str = "张三") -> dict:
    response = client.post("/api/members", json={"name": name})
    assert response.status_code == 201
    return response.json()["data"]


def test_book_member_and_stay_crud(tmp_path: Path) -> None:
    client = make_client(tmp_path)
    book = create_book(client)
    book_id = book["id"]
    assert (tmp_path / "books" / str(book_id) / "stays.json").exists()

    member = create_member(client)
    assert (tmp_path / "members.json").exists()
    member_id = member["id"]
    assert isinstance(member_id, int)
    assert "joinDate" not in member
    stay = client.post(
        f"/api/books/{book_id}/stays",
        json={"memberId": member_id, "joinDate": "2026-03-01"},
    )
    assert stay.status_code == 201
    assert stay.json()["data"]["bookId"] == book_id
    assert stay.json()["data"]["memberId"] == member_id

    member_detail = client.get(f"/api/members/{member_id}").json()["data"]
    assert member_detail["member"] == member
    assert member_detail["stayCount"] == 1
    assert member_detail["stays"][0]["bookId"] == book_id
    stay_detail = client.get(
        f"/api/books/{book_id}/stays/{member_id}"
    ).json()["data"]
    assert stay_detail["member"]["name"] == "张三"

    renamed = client.patch(f"/api/members/{member_id}", json={"name": "张小三"})
    assert renamed.status_code == 200
    changed = client.patch(
        f"/api/books/{book_id}/stays/{member_id}",
        json={"leaveDate": "2026-03-31"},
    )
    assert changed.status_code == 200
    assert changed.json()["data"]["leaveDate"] == "2026-03-31"
    assert client.patch(
        f"/api/books/{book_id}/stays/{member_id}", json={"leaveDate": None}
    ).json()["data"]["leaveDate"] is None

    assert client.delete(f"/api/members/{member_id}").status_code == 409
    assert client.delete(f"/api/books/{book_id}").status_code == 409
    assert client.delete(f"/api/books/{book_id}/stays/{member_id}").status_code == 204
    assert client.delete(f"/api/members/{member_id}").status_code == 204
    assert client.delete(f"/api/books/{book_id}").status_code == 204


def test_stay_isolation_and_deletion_protection(tmp_path: Path) -> None:
    client = make_client(tmp_path)
    first = create_book(client, "甲账本")["id"]
    second = create_book(client, "乙账本")["id"]
    member_id = create_member(client, "李四")["id"]
    client.post(
        f"/api/books/{first}/stays",
        json={"memberId": member_id, "joinDate": "2026-01-01"},
    )
    assert client.get(f"/api/books/{second}/stays").json()["data"]["total"] == 0
    assert client.get(f"/api/books/{second}/stays/{member_id}").status_code == 404

    bill = client.post(
        f"/api/books/{first}/bills",
        json={
            "title": "电费", "amountCents": 100, "date": "2026-01-31",
            "method": "EVEN", "participants": [member_id], "payerId": member_id,
        },
    )
    assert bill.status_code == 201
    response = client.delete(f"/api/books/{first}/stays/{member_id}")
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "STAY_IN_USE"
    assert client.delete(f"/api/members/{member_id}").status_code == 409


def test_validation_and_old_route_removed(tmp_path: Path) -> None:
    client = make_client(tmp_path)
    book_id = create_book(client)["id"]
    member_id = create_member(client, "王五")["id"]
    invalid = client.post(
        f"/api/books/{book_id}/stays",
        json={
            "memberId": member_id, "joinDate": "2026-04-01",
            "leaveDate": "2026-03-31",
        },
    )
    assert invalid.status_code == 422
    assert client.post(
        f"/api/books/{book_id}/stays",
        json={"memberId": 999, "joinDate": "2026-03-01"},
    ).status_code == 404
    assert client.get(f"/api/books/{book_id}/members").status_code == 404
    paths = client.get("/openapi.json").json()["paths"]
    assert not any("/members" in path and "/books/" in path for path in paths)


def test_concurrent_numeric_member_creation(tmp_path: Path) -> None:
    app = create_app(Settings(data_dir=tmp_path, seed_demo_books=False))

    def post_member(number: int) -> int:
        with TestClient(app) as client:
            response = client.post("/api/members", json={"name": f"成员{number}"})
            assert response.status_code == 201
            return response.json()["data"]["id"]

    with ThreadPoolExecutor(max_workers=5) as executor:
        member_ids = list(executor.map(post_member, range(5)))
    assert len(set(member_ids)) == 5
    assert sorted(member_ids) == [1, 2, 3, 4, 5]
    assert FileStore(tmp_path).read_json(tmp_path / "sequences.json")["nextMemberId"] == 6


def test_member_can_be_created_before_first_book(tmp_path: Path) -> None:
    client = make_client(tmp_path)
    assert create_member(client)["id"] == 1
    assert create_book(client)["id"] == 1
    sequences = FileStore(tmp_path).read_json(tmp_path / "sequences.json")
    assert sequences == {"nextMemberId": 2, "nextBookId": 2}
