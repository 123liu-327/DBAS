import json
import os
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.crud.books import list_books
from app.main import create_app
from app.models.bill import Bill
from app.models.member import Member
from app.models.stay import Stay
from app.schemas.book import BookCreate
from app.services.book_service import create_book
from app.services.splitting_service import calculate_shares
from app.storage import FileStore, StorageError
from app.storage.migrate import migrate_legacy
from app.storage.migrate_members import migrate_member_storage


def create_book_in_process(root: str, number: int) -> int:
    return create_book(
        FileStore(Path(root)), BookCreate(name=f"并发账本{number}")
    ).id


def test_processes_allocate_unique_numeric_ids(tmp_path: Path) -> None:
    with ProcessPoolExecutor(max_workers=5) as executor:
        ids = list(executor.map(create_book_in_process, [str(tmp_path)] * 5, range(5)))
    assert sorted(ids) == [1, 2, 3, 4, 5]
    assert len(list_books(FileStore(tmp_path))) == 5


def test_initial_seed_is_startup_only_complete_and_idempotent(tmp_path: Path) -> None:
    app = create_app(Settings(data_dir=tmp_path))
    assert not (tmp_path / "sequences.json").exists()
    assert not (tmp_path / "books").exists()

    with TestClient(app) as client:
        first = client.get("/api/books?page=1&pageSize=10").json()["data"]
        assert first["total"] == 10
        assert {book["id"] for book in first["list"]} == set(range(1, 11))
        assert all(book["description"] for book in first["list"])
        for book_id in range(1, 11):
            directory = tmp_path / "books" / str(book_id)
            assert (directory / "book.json").is_file()
            assert (directory / "stays.json").is_file()
            assert (directory / "bills.jsonl").is_file()
            assert FileStore(tmp_path).read_json(directory / "stays.json") == {"stays": []}
            assert (directory / "bills.jsonl").read_text(encoding="utf-8") == ""

    with TestClient(create_app(Settings(data_dir=tmp_path))) as client:
        assert client.get("/api/books").json()["data"]["total"] == 10
        created = client.post("/api/books", json={"name": "新账本"}).json()["data"]
        assert created["id"] == 11
        assert created["description"] is None


def test_existing_or_previously_deleted_books_are_not_seeded(tmp_path: Path) -> None:
    app = create_app(Settings(data_dir=tmp_path, seed_demo_books=False))
    client = TestClient(app)
    book = client.post("/api/books", json={"name": "我的账本"}).json()["data"]
    assert book["id"] == 1
    with TestClient(create_app(Settings(data_dir=tmp_path))) as started:
        assert started.get("/api/books").json()["data"]["total"] == 1
        assert started.delete("/api/books/1").status_code == 204

    with TestClient(create_app(Settings(data_dir=tmp_path))) as restarted:
        assert restarted.get("/api/books").json()["data"]["total"] == 0
        replacement = restarted.post("/api/books", json={"name": "新账本"}).json()["data"]
        assert replacement["id"] == 2


def test_seed_resumes_after_interrupted_publish(tmp_path: Path) -> None:
    original = FileStore.publish_book
    interrupted = False

    def publish_once(self: FileStore, book_id: int, record: dict) -> None:
        nonlocal interrupted
        if book_id == 4 and not interrupted:
            interrupted = True
            raise OSError("interrupted")
        original(self, book_id, record)

    with patch.object(FileStore, "publish_book", publish_once):
        with pytest.raises(OSError, match="interrupted"):
            with TestClient(create_app(Settings(data_dir=tmp_path))):
                pass
    assert not (tmp_path / "books" / "4").exists()
    assert FileStore(tmp_path).read_json(tmp_path / "sequences.json")["seedInProgress"]

    with TestClient(create_app(Settings(data_dir=tmp_path))) as client:
        assert client.get("/api/books").json()["data"]["total"] == 10
    assert not FileStore(tmp_path).read_json(tmp_path / "sequences.json").get("seedInProgress")
    assert not list((tmp_path / "books").glob(".pending-*"))


def test_failed_directory_publish_leaves_no_visible_book(tmp_path: Path) -> None:
    store = FileStore(tmp_path)
    real_replace = os.replace

    def fail_directory(source: Path, target: Path) -> None:
        if Path(source).is_dir():
            raise OSError("interrupted")
        real_replace(source, target)

    with patch("app.storage.files.os.replace", side_effect=fail_directory):
        with pytest.raises(OSError, match="interrupted"):
            store.publish_book(1, {"id": 1, "name": "演示"})
    assert not store.book_dir(1).exists()
    assert not list(store.books_dir.glob(".pending-*"))


def test_book_description_and_numeric_id_in_api(tmp_path: Path) -> None:
    client = TestClient(create_app(Settings(data_dir=tmp_path, seed_demo_books=False)))
    response = client.post(
        "/api/books", json={"name": " 3栋402 ", "description": " 公共费用记录 "},
    )
    assert response.status_code == 201
    book = response.json()["data"]
    assert book["id"] == 1
    assert book["name"] == "3栋402"
    assert book["description"] == "公共费用记录"
    assert client.get("/api/books/1").json()["data"]["book"]["description"] == book[
        "description"
    ]
    assert client.get("/api/books").json()["data"]["list"][0]["description"] == book[
        "description"
    ]
    changed = client.patch("/api/books/1", json={"description": "第二学期"})
    assert changed.status_code == 200
    assert changed.json()["data"]["name"] == book["name"]
    assert changed.json()["data"]["description"] == "第二学期"
    assert changed.json()["data"]["createdAt"] == book["createdAt"]
    cleared = client.patch("/api/books/1", json={"description": None})
    assert cleared.json()["data"]["description"] is None
    assert client.patch("/api/books/1", json={"name": None}).status_code == 422
    too_long = client.post("/api/books", json={"name": "无效", "description": "x" * 501})
    assert too_long.status_code == 422
    assert client.get("/api/books/invalid").status_code == 422


def test_legacy_example_migration_preserves_references_and_shares(tmp_path: Path) -> None:
    source = Path(__file__).resolve().parents[1] / "examples" / "legacy-data"
    target = tmp_path / "converted"
    mapping = migrate_legacy(source, target)
    assert mapping == {"book_demo": 1}
    assert (source / "books.json").is_file()
    store = FileStore(target)
    books = list_books(store)
    assert len(books) == 1 and books[0].id == 1
    members = {
        item.id: item for item in (
            Member.model_validate(raw)
            for raw in store.read_json(store.members_path)["members"]
        )
    }
    stays = {
        item.member_id: item for item in (
            Stay.model_validate(raw)
            for raw in store.read_json(store.stays_path(1))["stays"]
        )
    }
    assert set(members) == set(stays)
    bills = [Bill.model_validate(raw) for raw in store.read_jsonl(store.bills_path(1))]
    assert {bill.book_id for bill in bills} == {1}
    assert [bill.id for bill in bills] == ["b_electric", "b_supplies", "b_draft"]
    for bill in bills[:2]:
        total = sum(item.share_cents for item in calculate_shares(bill, stays))
        assert total == bill.amount_cents
    assert store.read_json(store.sequences_path)["nextBookId"] == 2
    assert store.read_json(store.sequences_path)["nextMemberId"] == 4
    with pytest.raises(ValueError, match="new directory"):
        migrate_legacy(source, target)


def test_numeric_book_member_split_requires_explicit_migration(tmp_path: Path) -> None:
    data = tmp_path / "data"
    book_dir = data / "books" / "1"
    book_dir.mkdir(parents=True)
    (book_dir / "book.json").write_text(json.dumps({
        "id": 1, "name": "旧账本", "description": None,
        "createdAt": "2026-03-01T00:00:00Z",
        "updatedAt": "2026-03-01T00:00:00Z",
    }), encoding="utf-8")
    (book_dir / "members.json").write_text(json.dumps({"members": [{
        "id": "m1", "name": "甲", "joinDate": "2026-03-01", "leaveDate": None,
        "createdAt": "2026-03-01T00:00:00Z",
        "updatedAt": "2026-03-01T00:00:00Z",
    }]}), encoding="utf-8")
    (book_dir / "bills.jsonl").write_text(json.dumps({
        "id": "b1", "bookId": 1, "title": "电费", "amountCents": 100,
        "date": "2026-03-31", "method": "EVEN", "participants": ["m1"],
        "payerId": "m1", "status": "POSTED", "attachments": [],
        "createdAt": "2026-03-31T00:00:00Z",
        "updatedAt": "2026-03-31T00:00:00Z",
    }) + "\n", encoding="utf-8")
    (data / "sequences.json").write_text('{"nextBookId":2}\n', encoding="utf-8")

    with pytest.raises(StorageError, match="migrate_members"):
        with TestClient(create_app(Settings(data_dir=data, seed_demo_books=False))):
            pass
    result = migrate_member_storage(data)
    assert result["migrated"] and result["members"] == 1
    assert Path(result["backup"]).is_dir()
    assert not (data / "books" / "1" / "members.json").exists()
    assert (data / "books" / "1" / "stays.json").is_file()
    with TestClient(create_app(Settings(data_dir=data, seed_demo_books=False))) as client:
        detail = client.get("/api/books/1/bills/b1").json()["data"]
        assert detail["bill"]["participants"] == [1]
        assert detail["shares"][0]["memberId"] == 1
