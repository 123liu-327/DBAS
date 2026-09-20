"""Low-level bill records; business validation lives in bill_service."""

from app.core.exceptions import AppError
from app.crud.books import require_book
from app.models.bill import Bill
from app.storage import FileStore


def list_bills(store: FileStore, book_id: int) -> list[Bill]:
    require_book(store, book_id)
    return [Bill.model_validate(item) for item in store.read_jsonl(store.bills_path(book_id))]


def require_bill(store: FileStore, book_id: int, bill_id: str) -> Bill:
    bill = next((item for item in list_bills(store, book_id) if item.id == bill_id), None)
    if bill is None:
        raise AppError("BILL_NOT_FOUND", "账单不存在", status_code=404, field="billId")
    return bill


def insert_bill(store: FileStore, bill: Bill) -> None:
    store.update_jsonl(
        store.bills_path(bill.book_id),
        lambda rows: [*rows, bill.model_dump(mode="json")],
        book_id=bill.book_id,
    )


def replace_bill(store: FileStore, bill: Bill) -> None:
    def replace(rows: list[dict]) -> list[dict]:
        for index, row in enumerate(rows):
            if row["id"] == bill.id:
                rows[index] = bill.model_dump(mode="json")
                return rows
        raise AppError("BILL_NOT_FOUND", "账单不存在", status_code=404, field="billId")

    store.update_jsonl(store.bills_path(bill.book_id), replace, book_id=bill.book_id)


def remove_bill(store: FileStore, book_id: int, bill_id: str) -> None:
    def remove(rows: list[dict]) -> list[dict]:
        filtered = [row for row in rows if row["id"] != bill_id]
        if len(filtered) == len(rows):
            raise AppError("BILL_NOT_FOUND", "账单不存在", status_code=404, field="billId")
        return filtered

    store.update_jsonl(store.bills_path(book_id), remove, book_id=book_id)
