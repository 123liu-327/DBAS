"""The deliverable text example must remain readable by the real file adapter."""

from pathlib import Path

from app.crud.books import list_books
from app.models import Bill, Book, Member, Stay
from app.services.splitting_service import calculate_shares
from app.storage import FileStore


def test_text_data_example_is_valid_and_balanced() -> None:
    root = Path(__file__).resolve().parents[1] / "examples" / "data"
    store = FileStore(root)
    books = list_books(store)
    assert len(books) == 1
    assert isinstance(books[0], Book)
    assert isinstance(books[0].id, int)
    book_id = books[0].id
    members = {
        item.id: item
        for item in (
            Member.model_validate(raw)
            for raw in store.read_json(store.members_path)["members"]
        )
    }
    stays = {
        item.member_id: item
        for item in (
            Stay.model_validate(raw)
            for raw in store.read_json(store.stays_path(book_id))["stays"]
        )
    }
    assert set(members) == set(stays)
    bills = [Bill.model_validate(raw) for raw in store.read_jsonl(store.bills_path(book_id))]
    assert [bill.status.value for bill in bills] == ["POSTED", "POSTED", "DRAFT"]
    shares = [calculate_shares(bill, stays) for bill in bills[:2]]
    assert [item.share_cents for item in shares[0]] == [2316, 1569, 2315]
    assert [item.share_cents for item in shares[1]] == [3333, 1667]
    assert all(sum(item.share_cents for item in group) == bill.amount_cents
               for group, bill in zip(shares, bills[:2], strict=True))
