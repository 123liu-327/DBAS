import csv
from io import StringIO
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.main import create_app


def seeded_client(tmp_path: Path) -> tuple[TestClient, int, list[int]]:
    client = TestClient(create_app(Settings(data_dir=tmp_path, seed_demo_books=False)))
    book_id = client.post("/api/books", json={"name": "402"}).json()["data"]["id"]
    ids = []
    for name in ["张三", "李四", "王五", "赵六"]:
        member_id = client.post("/api/members", json={"name": name}).json()["data"]["id"]
        client.post(
            f"/api/books/{book_id}/stays",
            json={"memberId": member_id, "joinDate": "2026-01-01"},
        )
        ids.append(member_id)
    return client, book_id, ids


def add_bill(
    client: TestClient, book_id: int, title: str, amount: int, payer: int,
    participants: list[int], month: str = "2026-03",
) -> str:
    response = client.post(
        f"/api/books/{book_id}/bills",
        json={
            "title": title, "amountCents": amount, "date": f"{month}-15",
            "method": "EVEN", "payerId": payer, "participants": participants,
        },
    )
    assert response.status_code == 201, response.text
    return response.json()["data"]["id"]


def test_t11_t12_settlement_csv_and_trend(tmp_path: Path) -> None:
    client, book_id, ids = seeded_client(tmp_path)
    add_bill(client, book_id, "电费", 40000, ids[0], ids)
    add_bill(client, book_id, "水费", 20000, ids[1], ids)
    add_bill(client, book_id, "纸巾", 10000, ids[2], ids[:3])
    prefix = f"/api/books/{book_id}"

    plan = client.post(
        f"{prefix}/settlement-plans",
        json={"startMonth": "2026-03", "endMonth": "2026-03"},
    )
    assert plan.status_code == 200, plan.text
    data = plan.json()["data"]
    assert [item["netCents"] for item in data["balances"]] == [
        21666, 1667, -8333, -15000
    ]
    assert data["netSumCents"] == 0 and data["balanced"]
    assert len(data["transfers"]) == 3
    remaining = {item["memberId"]: item["netCents"] for item in data["balances"]}
    for transfer in data["transfers"]:
        remaining[transfer["fromMemberId"]] += transfer["amountCents"]
        remaining[transfer["toMemberId"]] -= transfer["amountCents"]
    assert all(value == 0 for value in remaining.values())

    exported = client.get(f"{prefix}/exports/bills.csv?month=2026-03")
    assert exported.status_code == 200
    assert "export_2026-03.csv" in exported.headers["content-disposition"]
    rows = list(csv.DictReader(StringIO(exported.content.decode("utf-8"))))
    assert list(rows[0]) == [
        "bill_id", "title", "bill_date", "payer_name", "amount_cents",
        "method", "participant_name", "share_cents",
    ]
    for bill_id in {row["bill_id"] for row in rows}:
        bill_rows = [row for row in rows if row["bill_id"] == bill_id]
        assert sum(int(row["share_cents"]) for row in bill_rows) == int(
            bill_rows[0]["amount_cents"]
        )

    trend = client.get(f"{prefix}/statistics/monthly?endMonth=2026-03")
    assert trend.status_code == 200
    points = trend.json()["data"]
    assert [item["month"] for item in points] == [
        "2025-10", "2025-11", "2025-12", "2026-01", "2026-02", "2026-03"
    ]
    assert [item["totalCents"] for item in points] == [0, 0, 0, 0, 0, 70000]
    assert points[-1]["perCapitaCents"] == 17500


def test_settlement_month_range_excludes_drafts_and_outside_bills(tmp_path: Path) -> None:
    client, book_id, ids = seeded_client(tmp_path)
    add_bill(client, book_id, "三月账单", 100, ids[0], ids[:2])
    add_bill(client, book_id, "四月账单", 80, ids[1], ids[:2], month="2026-04")
    add_bill(client, book_id, "五月账单", 200, ids[1], ids[:2], month="2026-05")
    draft = client.post(
        f"/api/books/{book_id}/bills",
        json={"title": "未入账", "status": "DRAFT", "amountCents": 1000,
              "date": "2026-03-15", "method": "EVEN",
              "payerId": ids[1], "participants": ids[:2]},
    )
    assert draft.status_code == 201

    def plan(start: str, end: str) -> dict:
        response = client.post(
            f"/api/books/{book_id}/settlement-plans",
            json={"startMonth": start, "endMonth": end},
        )
        assert response.status_code == 200, response.text
        return response.json()["data"]

    march = plan("2026-03", "2026-03")
    assert [item["netCents"] for item in march["balances"]] == [50, -50, 0, 0]
    combined = plan("2026-03", "2026-04")
    assert [item["netCents"] for item in combined["balances"]] == [10, -10, 0, 0]
    assert combined["netSumCents"] == 0 and combined["balanced"]
    remaining = {item["memberId"]: item["netCents"] for item in combined["balances"]}
    for transfer in combined["transfers"]:
        remaining[transfer["fromMemberId"]] += transfer["amountCents"]
        remaining[transfer["toMemberId"]] -= transfer["amountCents"]
    assert all(value == 0 for value in remaining.values())
    assert client.post(
        f"/api/books/{book_id}/settlement-plans",
        json={"startMonth": "2026-04", "endMonth": "2026-03"},
    ).status_code == 422


def test_attachment_upload_download_limit_and_isolation(tmp_path: Path) -> None:
    client, book_id, ids = seeded_client(tmp_path)
    bill_id = add_bill(client, book_id, "电费", 1000, ids[0], ids[:2])
    prefix = f"/api/books/{book_id}/bills/{bill_id}/attachments"
    bill_path = f"/api/books/{book_id}/bills/{bill_id}"
    original_bill = client.get(bill_path).json()["data"]["bill"]
    png = b"\x89PNG\r\n\x1a\n" + b"image bytes"
    first = client.post(prefix, files={"file": ("receipt.png", png, "image/png")})
    assert first.status_code == 201, first.text
    attachment = first.json()["data"]
    assert attachment["fileName"] == "receipt.png"
    assert attachment["relativePath"].startswith("attachments/")
    after_upload = client.get(bill_path).json()["data"]["bill"]
    assert after_upload["createdAt"] == original_bill["createdAt"]
    assert after_upload["updatedAt"] >= original_bill["updatedAt"]
    assert len(client.get(prefix).json()["data"]["list"]) == 1
    downloaded = client.get(f"{prefix}/{attachment['id']}")
    assert downloaded.status_code == 200 and downloaded.content == png
    assert client.post(
        prefix, files={"file": ("fake.png", b"not an image", "image/png")}
    ).status_code == 422
    assert client.post(
        prefix, files={"file": ("bad.exe", b"x", "application/octet-stream")}
    ).status_code == 422
    assert client.post(
        prefix,
        files={"file": ("large.pdf", b"%PDF-" + b"x" * (10 * 1024 * 1024),
                        "application/pdf")},
    ).status_code == 422

    for number in range(2):
        assert client.post(
            prefix, files={"file": (f"receipt{number}.png", png, "image/png")}
        ).status_code == 201
    assert client.post(
        prefix, files={"file": ("extra.png", png, "image/png")}
    ).status_code == 409
    other_book = client.post("/api/books", json={"name": "其他"}).json()["data"]["id"]
    other_prefix = f"/api/books/{other_book}/bills/{bill_id}/attachments"
    assert client.get(f"{other_prefix}/{attachment['id']}").status_code == 404
    assert client.delete(f"{prefix}/{attachment['id']}").status_code == 204
    assert client.get(f"{prefix}/{attachment['id']}").status_code == 404
    after_delete = client.get(bill_path).json()["data"]["bill"]
    assert after_delete["createdAt"] == original_bill["createdAt"]
    assert after_delete["updatedAt"] >= after_upload["updatedAt"]
    assert client.delete(f"/api/books/{book_id}/bills/{bill_id}").status_code == 204
    assert not list((tmp_path / "books" / str(book_id) / "attachments" / bill_id).glob("*.png"))


@pytest.mark.parametrize(
    ("filename", "media_type", "contents"),
    [
        ("receipt.png", "image/png", b"\x89PNG\r\n\x1a\ncontents"),
        ("receipt.jpg", "image/jpeg", b"\xff\xd8\xffcontents"),
        ("receipt.webp", "image/webp", b"RIFF\x00\x00\x00\x00WEBPcontents"),
        ("receipt.pdf", "application/pdf", b"%PDF-1.7 contents"),
    ],
)
def test_supported_attachment_formats(
    tmp_path: Path, filename: str, media_type: str, contents: bytes,
) -> None:
    client, book_id, ids = seeded_client(tmp_path)
    bill_id = add_bill(client, book_id, "票据", 100, ids[0], ids[:2])
    prefix = f"/api/books/{book_id}/bills/{bill_id}/attachments"
    uploaded = client.post(prefix, files={"file": (filename, contents, media_type)})
    assert uploaded.status_code == 201, uploaded.text
    attachment = uploaded.json()["data"]
    assert attachment["contentType"] == media_type
    assert client.get(f"{prefix}/{attachment['id']}").content == contents
