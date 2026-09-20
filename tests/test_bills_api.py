from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from pathlib import Path

from fastapi.testclient import TestClient

from app.core.config import Settings
from app.main import create_app
from app.storage import FileStore


def setup_book(client: TestClient) -> tuple[int, list[int]]:
    book_id = client.post("/api/books", json={"name": "宿舍"}).json()["data"]["id"]
    ids = []
    for name, join in [("甲", "2026-03-01"), ("乙", "2026-03-11"),
                       ("丙", "2026-03-01")]:
        member_id = client.post("/api/members", json={"name": name}).json()["data"]["id"]
        response = client.post(
            f"/api/books/{book_id}/stays",
            json={"memberId": member_id, "joinDate": join},
        )
        assert response.status_code == 201
        ids.append(member_id)
    return book_id, ids


def bill_payload(ids: list[int], **changes: object) -> dict:
    result = {
        "title": "3月电费", "amountCents": 6200, "date": "2026-03-31",
        "method": "BY_DAYS", "participants": ids, "payerId": ids[0],
        "period": {"start": "2026-03-01", "end": "2026-03-31"},
    }
    result.update(changes)
    return result


def test_bill_preview_crud_and_monthly_shares(tmp_path: Path) -> None:
    client = TestClient(create_app(Settings(data_dir=tmp_path, seed_demo_books=False)))
    book_id, ids = setup_book(client)
    prefix = f"/api/books/{book_id}"
    payload = bill_payload(ids)
    preview = client.post(f"{prefix}/bill-previews", json=payload)
    assert preview.status_code == 200
    assert [item["shareCents"] for item in preview.json()["data"]["shares"]] == [
        2316, 1569, 2315
    ]
    assert client.get(f"{prefix}/bills").json()["data"] == {
        "list": [], "total": 0, "hasMore": False,
    }

    created = client.post(f"{prefix}/bills", json=payload)
    assert created.status_code == 201 and created.json()["code"] == 201
    bill = created.json()["data"]
    bill_id = bill["id"]
    assert bill["status"] == "POSTED"
    detail = client.get(f"{prefix}/bills/{bill_id}").json()["data"]
    assert [item["shareCents"] for item in detail["shares"]] == [2316, 1569, 2315]
    assert len(client.get(f"{prefix}/bills?month=2026-03").json()["data"]["list"]) == 1
    assert client.get(f"{prefix}/bills?month=2026-04").json()["data"]["total"] == 0
    totals = client.get(f"{prefix}/statistics/member-shares?month=2026-03")
    assert [item["shareCents"] for item in totals.json()["data"]["shares"]] == [
        2316, 1569, 2315
    ]

    changed = client.patch(f"{prefix}/bills/{bill_id}", json={"amountCents": 8300})
    assert changed.status_code == 200
    assert changed.json()["data"]["createdAt"] == bill["createdAt"]
    assert [item["shareCents"] for item in client.get(
        f"{prefix}/bills/{bill_id}"
    ).json()["data"]["shares"]] == [3100, 2100, 3100]
    assert [item["shareCents"] for item in client.get(
        f"{prefix}/statistics/member-shares?month=2026-03"
    ).json()["data"]["shares"]] == [3100, 2100, 3100]
    client.patch(f"{prefix}/stays/{ids[1]}", json={"joinDate": "2026-03-01"})
    assert [item["effectiveDays"] for item in client.get(
        f"{prefix}/bills/{bill_id}"
    ).json()["data"]["shares"]] == [31, 31, 31]
    moved = client.patch(f"{prefix}/bills/{bill_id}", json={"date": "2026-04-01"})
    assert moved.status_code == 200
    assert client.get(f"{prefix}/bills?month=2026-03").json()["data"]["total"] == 0
    assert len(client.get(f"{prefix}/bills?month=2026-04").json()["data"]["list"]) == 1
    assert all(item["shareCents"] == 0 for item in client.get(
        f"{prefix}/statistics/member-shares?month=2026-03"
    ).json()["data"]["shares"])
    deleted = client.delete(f"{prefix}/bills/{bill_id}")
    assert deleted.status_code == 204 and not deleted.content
    assert client.get(f"{prefix}/bills/{bill_id}").status_code == 404


def test_draft_posting_and_invalid_references(tmp_path: Path) -> None:
    client = TestClient(create_app(Settings(data_dir=tmp_path, seed_demo_books=False)))
    book_id, ids = setup_book(client)
    prefix = f"/api/books/{book_id}"
    draft = client.post(f"{prefix}/bills", json={"status": "DRAFT", "title": "待补"})
    assert draft.status_code == 201
    bill_id = draft.json()["data"]["id"]
    assert client.get(f"{prefix}/bills/{bill_id}").json()["data"]["shares"] == []
    assert client.get(f"{prefix}/statistics/member-shares?month=2026-03").json()[
        "data"
    ]["shares"][0]["shareCents"] == 0
    incomplete = client.patch(f"{prefix}/bills/{bill_id}", json={"status": "POSTED"})
    assert incomplete.status_code == 422
    posted = client.patch(f"{prefix}/bills/{bill_id}", json=bill_payload(ids, status="POSTED"))
    assert posted.status_code == 200
    assert posted.json()["data"]["status"] == "POSTED"
    assert client.patch(f"{prefix}/bills/{bill_id}", json={"status": "DRAFT"}).status_code == 409
    for reserved in ("LOCKED", "SETTLED"):
        assert client.post(
            f"{prefix}/bills", json=bill_payload(ids, status=reserved)
        ).status_code == 422
        assert client.patch(
            f"{prefix}/bills/{bill_id}", json={"status": reserved}
        ).status_code == 422
    assert client.get(f"{prefix}/bills/{bill_id}").json()["data"]["bill"]["status"] == "POSTED"
    assert client.post(f"{prefix}/bills", json=bill_payload([ids[0], 999])).status_code == 422
    other_book = client.post("/api/books", json={"name": "其他"}).json()["data"]["id"]
    assert client.get(f"/api/books/{other_book}/bills/{bill_id}").status_code == 404
    assert client.post(
        f"{prefix}/bill-previews", json=bill_payload(ids, amountCents=0)
    ).status_code == 422


def test_audit_timestamps_across_repeated_book_member_bill_edits(tmp_path: Path) -> None:
    client = TestClient(create_app(Settings(data_dir=tmp_path, seed_demo_books=False)))
    book_id, ids = setup_book(client)
    bill = client.post(f"/api/books/{book_id}/bills", json=bill_payload(ids)).json()["data"]
    targets = [
        (f"/api/books/{book_id}", {"name": "宿舍甲"}, {"name": "宿舍乙"}),
        (f"/api/members/{ids[0]}",
         {"name": "甲一"}, {"name": "甲二"}),
        (f"/api/books/{book_id}/bills/{bill['id']}",
         {"title": "电费一"}, {"title": "电费二"}),
    ]
    for path, first_change, second_change in targets:
        original = client.get(path).json()["data"]
        for key in ("book", "member", "bill"):
            if key in original:
                original = original[key]
                break
        first = client.patch(path, json=first_change).json()["data"]
        second = client.patch(path, json=second_change).json()["data"]
        assert first["createdAt"] == second["createdAt"] == original["createdAt"]
        stamps = [datetime.fromisoformat(item["updatedAt"])
                  for item in (original, first, second)]
        assert all(stamp.tzinfo is not None and stamp.utcoffset() == UTC.utcoffset(None)
                   for stamp in stamps)
        assert stamps[0] < stamps[1] < stamps[2]


def test_stay_change_cannot_invalidate_all_by_days_shares(tmp_path: Path) -> None:
    client = TestClient(create_app(Settings(data_dir=tmp_path, seed_demo_books=False)))
    book_id = client.post("/api/books", json={"name": "宿舍"}).json()["data"]["id"]
    member_id = client.post("/api/members", json={"name": "甲"}).json()["data"]["id"]
    client.post(
        f"/api/books/{book_id}/stays",
        json={"memberId": member_id, "joinDate": "2026-03-01"},
    )
    response = client.post(
        f"/api/books/{book_id}/bills",
        json=bill_payload([member_id], amountCents=100),
    )
    assert response.status_code == 201
    changed = client.patch(
        f"/api/books/{book_id}/stays/{member_id}",
        json={"joinDate": "2026-04-01"},
    )
    assert changed.status_code == 422
    assert client.get(f"/api/books/{book_id}/stays/{member_id}").json()[
        "data"
        ]["stay"]["joinDate"] == "2026-03-01"


def test_five_concurrent_bill_creates_preserve_all_records(tmp_path: Path) -> None:
    app = create_app(Settings(data_dir=tmp_path, seed_demo_books=False))
    client = TestClient(app)
    book_id, ids = setup_book(client)

    def post_bill(index: int) -> int:
        with TestClient(app) as concurrent_client:
            response = concurrent_client.post(
                f"/api/books/{book_id}/bills", json=bill_payload(ids, title=f"账单{index}")
            )
            return response.status_code

    with ThreadPoolExecutor(max_workers=5) as executor:
        assert list(executor.map(post_bill, range(5))) == [201] * 5
    assert client.get(f"/api/books/{book_id}/bills").json()["data"]["total"] == 5


def test_locked_bill_blocks_share_changing_stay_edit(tmp_path: Path) -> None:
    client = TestClient(create_app(Settings(data_dir=tmp_path, seed_demo_books=False)))
    book_id, ids = setup_book(client)
    created = client.post(
        f"/api/books/{book_id}/bills", json=bill_payload(ids)
    ).json()["data"]
    store = FileStore(tmp_path)
    rows = store.read_jsonl(store.bills_path(book_id))
    rows[0]["status"] = "LOCKED"
    store.write_jsonl(store.bills_path(book_id), rows, book_id=book_id)
    response = client.patch(
        f"/api/books/{book_id}/stays/{ids[1]}",
        json={"joinDate": "2026-03-01"},
    )
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "STAY_LOCKED"
    assert client.get(f"/api/books/{book_id}/bills/{created['id']}").status_code == 200
