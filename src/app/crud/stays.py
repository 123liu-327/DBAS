"""Per-book stay records keyed by (bookId, memberId)."""

from pydantic import ValidationError

from app.core.exceptions import AppError
from app.crud import members as member_crud
from app.crud.books import require_book, touch_book
from app.models.stay import Stay
from app.schemas.stay import StayCreate, StayPatch
from app.storage import FileStore


def list_stays(store: FileStore, book_id: int) -> list[Stay]:
    require_book(store, book_id)
    data = store.read_json(store.stays_path(book_id), default={"stays": []})
    return [Stay.model_validate(item) for item in data["stays"]]


def get_stay(store: FileStore, book_id: int, member_id: int) -> Stay | None:
    return next(
        (item for item in list_stays(store, book_id) if item.member_id == member_id), None
    )


def require_stay(store: FileStore, book_id: int, member_id: int) -> Stay:
    stay = get_stay(store, book_id, member_id)
    if stay is None:
        raise AppError(
            "STAY_NOT_FOUND", "入住记录不存在", status_code=404, field="memberId"
        )
    return stay


def create_stay(store: FileStore, book_id: int, data: StayCreate) -> Stay:
    require_book(store, book_id)
    with store.index_lock():
        member_crud.require_member(store, data.member_id)
        with store.book_lock(book_id):
            require_book(store, book_id)
            if get_stay(store, book_id, data.member_id) is not None:
                raise AppError(
                    "STAY_EXISTS", "该成员已在此账本登记入住", status_code=409,
                    field="memberId",
                )
            stay = Stay(book_id=book_id, **data.model_dump(by_alias=False))

            def append(records: dict) -> dict:
                records["stays"].append(stay.model_dump(mode="json"))
                return records

            store.update_json(
                store.stays_path(book_id), append, default={"stays": []}, book_id=book_id
            )
            touch_book(store, book_id)
            return stay


def update_stay(
    store: FileStore, book_id: int, member_id: int, data: StayPatch
) -> Stay:
    with store.book_lock(book_id):
        updated: Stay | None = None

        def replace(records: dict) -> dict:
            nonlocal updated
            for position, raw in enumerate(records["stays"]):
                if raw["memberId"] == member_id:
                    try:
                        updated = Stay.model_validate(raw).with_updates(
                            **data.model_dump(exclude_unset=True, by_alias=False)
                        )
                    except ValidationError as exc:
                        raise AppError(
                            "INVALID_STAY", "退宿日期不能早于入住日期",
                            status_code=422, field="leaveDate",
                        ) from exc
                    records["stays"][position] = updated.model_dump(mode="json")
                    return records
            raise AppError(
                "STAY_NOT_FOUND", "入住记录不存在", status_code=404, field="memberId"
            )

        store.update_json(
            store.stays_path(book_id), replace, default={"stays": []}, book_id=book_id
        )
        touch_book(store, book_id)
        assert updated is not None
        return updated


def delete_stay(store: FileStore, book_id: int, member_id: int) -> None:
    with store.book_lock(book_id):
        require_stay(store, book_id, member_id)
        for bill in store.read_jsonl(store.bills_path(book_id)):
            if member_id in bill.get("participants", []) or bill.get("payerId") == member_id:
                raise AppError(
                    "STAY_IN_USE", "该入住成员已参与账单，不能删除入住记录",
                    status_code=409, field="memberId",
                )

        def remove(records: dict) -> dict:
            records["stays"] = [
                item for item in records["stays"] if item["memberId"] != member_id
            ]
            return records

        store.update_json(
            store.stays_path(book_id), remove, default={"stays": []}, book_id=book_id
        )
        touch_book(store, book_id)
