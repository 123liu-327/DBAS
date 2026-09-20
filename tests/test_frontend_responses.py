from pathlib import Path

from fastapi.testclient import TestClient

from app.core.config import Settings
from app.main import create_app


def test_frontend_pages_and_details_include_related_data(tmp_path: Path) -> None:
    client = TestClient(create_app(Settings(data_dir=tmp_path, seed_demo_books=False)))
    book = client.post("/api/books", json={"name": "宿舍"}).json()["data"]
    book_id = book["id"]
    prefix = f"/api/books/{book_id}"
    member_ids = []
    for name, joined in (("甲", "2026-03-01"), ("乙", "2026-03-11")):
        member_id = client.post("/api/members", json={"name": name}).json()["data"]["id"]
        client.post(
            f"{prefix}/stays", json={"memberId": member_id, "joinDate": joined}
        )
        member_ids.append(member_id)
    posted_payload = {
        "title": "电费", "amountCents": 4100, "date": "2026-03-31",
        "method": "BY_DAYS", "participants": member_ids, "payerId": member_ids[0],
        "period": {"start": "2026-03-01", "end": "2026-03-31"},
    }
    draft = client.post(
        f"{prefix}/bills", json={"status": "DRAFT", "title": "待补账单"},
    ).json()["data"]
    posted = client.post(f"{prefix}/bills", json=posted_payload).json()["data"]

    book_page = client.get("/api/books?page=1&pageSize=10").json()["data"]
    assert book_page["total"] == 1
    assert book_page["list"][0]["memberCount"] == 2
    assert book_page["list"][0]["billCount"] == 2
    assert book_page["list"][0]["lastActiveAt"] == book_page["list"][0]["updatedAt"]
    book_detail = client.get(prefix).json()["data"]
    assert book_detail["book"]["id"] == book_id
    assert [item["memberId"] for item in book_detail["stays"]] == member_ids
    assert book_detail["billStatusCounts"] == {
        "draft": 1, "posted": 1, "locked": 0, "settled": 0,
    }

    member_page = client.get("/api/members?page=1&pageSize=1").json()["data"]
    assert member_page["total"] == 2 and member_page["hasMore"]
    assert member_page["list"][0]["billCount"] == 1
    member_detail = client.get(f"/api/members/{member_ids[0]}").json()["data"]
    assert member_detail["member"]["id"] == member_ids[0]
    assert member_detail["stays"][0]["joinDate"] == "2026-03-01"
    assert (member_detail["billCount"], member_detail["paidBillCount"]) == (1, 1)

    bill_page = client.get(f"{prefix}/bills?month=2026-03").json()["data"]
    assert bill_page["total"] == 1
    item = bill_page["list"][0]
    assert item["id"] == posted["id"]
    assert item["payerName"] == "甲"
    assert item["participantCount"] == 2
    assert "shares" not in item
    detail = client.get(f"{prefix}/bills/{posted['id']}").json()["data"]
    assert detail["bill"]["id"] == posted["id"]
    assert detail["payer"]["name"] == "甲"
    assert [item["stay"]["joinDate"] for item in detail["participants"]] == [
        "2026-03-01", "2026-03-11",
    ]
    assert [share["stay"]["joinDate"] for share in detail["shares"]] == [
        "2026-03-01", "2026-03-11",
    ]
    assert sum(share["shareCents"] for share in detail["shares"]) == 4100
    assert [share["effectiveDays"] for share in detail["shares"]] == [31, 21]
    preview = client.post(f"{prefix}/bill-previews", json=posted_payload).json()["data"]
    assert sum(share["shareCents"] for share in preview["shares"]) == 4100
    assert [share["effectiveDays"] for share in preview["shares"]] == [31, 21]
    assert preview["payer"]["id"] == member_ids[0]
    assert len(preview["participants"]) == 2
    draft_detail = client.get(f"{prefix}/bills/{draft['id']}").json()["data"]
    assert draft_detail["shares"] == []
    assert draft_detail["payer"] is None


def test_frontend_detail_uses_current_stay_and_bill_values(tmp_path: Path) -> None:
    client = TestClient(create_app(Settings(data_dir=tmp_path, seed_demo_books=False)))
    book_id = client.post("/api/books", json={"name": "宿舍"}).json()["data"]["id"]
    prefix = f"/api/books/{book_id}"
    member_id = client.post("/api/members", json={"name": "甲"}).json()["data"]["id"]
    client.post(
        f"{prefix}/stays", json={"memberId": member_id, "joinDate": "2026-03-01"}
    )
    bill_id = client.post(
        f"{prefix}/bills",
        json={"title": "水费", "amountCents": 100, "date": "2026-03-31",
              "method": "BY_DAYS", "participants": [member_id], "payerId": member_id,
              "period": {"start": "2026-03-01", "end": "2026-03-31"}},
    ).json()["data"]["id"]
    client.patch(f"{prefix}/stays/{member_id}", json={"joinDate": "2026-03-15"})
    client.patch(f"/api/members/{member_id}", json={"name": "甲新名"})
    client.patch(f"{prefix}/bills/{bill_id}", json={"amountCents": 230})
    detail = client.get(f"{prefix}/bills/{bill_id}").json()["data"]
    assert detail["shares"][0]["stay"]["joinDate"] == "2026-03-15"
    assert detail["shares"][0]["effectiveDays"] == 17
    assert detail["shares"][0]["shareCents"] == 230
    assert detail["shares"][0]["member"]["name"] == "甲新名"
