"""Record collections use the same page/pageSize contract as the prior project."""

from pathlib import Path

from fastapi.testclient import TestClient

from app.core.config import Settings
from app.main import create_app


def test_books_members_bills_and_attachments_are_paginated(tmp_path: Path) -> None:
    client = TestClient(create_app(Settings(data_dir=tmp_path, seed_demo_books=False)))
    books = [
        client.post("/api/books", json={"name": f"账本{index}"}).json()["data"]["id"]
        for index in range(4)
    ]
    first_page = client.get("/api/books?page=1&pageSize=2").json()["data"]
    second_page = client.get("/api/books?page=2&pageSize=2").json()["data"]
    assert (first_page["total"], first_page["hasMore"], len(first_page["list"])) == (4, True, 2)
    assert (second_page["total"], second_page["hasMore"], len(second_page["list"])) == (
        4, False, 2,
    )
    assert {item["id"] for page in (first_page, second_page) for item in page["list"]} == set(
        books
    )
    assert client.get("/api/books?page=3&pageSize=2").json()["data"] == {
        "list": [], "total": 4, "hasMore": False,
    }

    book_id = books[0]
    prefix = f"/api/books/{book_id}"
    member_ids = []
    for index in range(3):
        member_id = client.post(
            "/api/members", json={"name": f"成员{index}"}
        ).json()["data"]["id"]
        client.post(
            f"{prefix}/stays", json={"memberId": member_id, "joinDate": "2026-03-01"}
        )
        member_ids.append(member_id)
    members = client.get(f"{prefix}/stays?page=2&pageSize=2").json()["data"]
    assert members["total"] == 3 and not members["hasMore"]
    assert [item["memberId"] for item in members["list"]] == member_ids[2:]
    assert client.get(f"/api/books/{books[1]}/stays").json()["data"]["total"] == 0

    bill_ids = []
    for index, month in enumerate(("03", "03", "03", "04")):
        response = client.post(
            f"{prefix}/bills",
            json={
                "title": f"账单{index}", "amountCents": 100,
                "date": f"2026-{month}-15", "method": "EVEN",
                "participants": member_ids[:2], "payerId": member_ids[0],
            },
        )
        assert response.status_code == 201, response.text
        bill_ids.append(response.json()["data"]["id"])
    march1 = client.get(f"{prefix}/bills?month=2026-03&page=1&pageSize=2").json()["data"]
    march2 = client.get(f"{prefix}/bills?month=2026-03&page=2&pageSize=2").json()["data"]
    assert (march1["total"], march1["hasMore"]) == (3, True)
    assert (march2["total"], march2["hasMore"]) == (3, False)
    assert [item["id"] for item in march1["list"] + march2["list"]] == bill_ids[:3]
    assert client.get(f"{prefix}/bills?month=2026-04").json()["data"]["total"] == 1
    assert client.get(f"{prefix}/bills").json()["data"]["total"] == 4

    attachments_url = f"{prefix}/bills/{bill_ids[0]}/attachments"
    png = b"\x89PNG\r\n\x1a\ncontents"
    for index in range(3):
        assert client.post(
            attachments_url, files={"file": (f"receipt{index}.png", png, "image/png")}
        ).status_code == 201
    att1 = client.get(f"{attachments_url}?page=1&pageSize=2").json()["data"]
    att2 = client.get(f"{attachments_url}?page=2&pageSize=2").json()["data"]
    assert (att1["total"], att1["hasMore"], len(att1["list"])) == (3, True, 2)
    assert (att2["total"], att2["hasMore"], len(att2["list"])) == (3, False, 1)


def test_invalid_pagination_is_rejected_on_every_collection(tmp_path: Path) -> None:
    client = TestClient(create_app(Settings(data_dir=tmp_path, seed_demo_books=False)))
    book_id = client.post("/api/books", json={"name": "宿舍"}).json()["data"]["id"]
    member_id = client.post("/api/members", json={"name": "甲"}).json()["data"]["id"]
    client.post(
        f"/api/books/{book_id}/stays",
        json={"memberId": member_id, "joinDate": "2026-03-01"},
    )
    bill_id = client.post(
        f"/api/books/{book_id}/bills",
        json={
            "title": "电费", "amountCents": 100, "date": "2026-03-31",
            "method": "EVEN", "participants": [member_id], "payerId": member_id,
        },
    ).json()["data"]["id"]
    paths = [
        "/api/books", "/api/members", f"/api/books/{book_id}/stays",
        f"/api/books/{book_id}/bills",
        f"/api/books/{book_id}/bills/{bill_id}/attachments",
    ]
    for path in paths:
        for query in ("page=0", "pageSize=0", "pageSize=101"):
            response = client.get(f"{path}?{query}")
            assert response.status_code == 422
            assert response.json()["error"]["field"] == query.split("=")[0]
