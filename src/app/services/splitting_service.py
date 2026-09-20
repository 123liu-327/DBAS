"""Book-aware validation and a single entry point for bill shares."""

from collections.abc import Mapping

from app.algorithms.splitting import split_bill
from app.core.exceptions import AppError
from app.crud import stays as stay_crud
from app.models.bill import Bill
from app.models.share import ShareDetail
from app.models.stay import Stay
from app.storage import FileStore


def stay_map(store: FileStore, book_id: int) -> dict[int, Stay]:
    return {stay.member_id: stay for stay in stay_crud.list_stays(store, book_id)}


def validate_members(bill: Bill, stays: Mapping[int, Stay]) -> None:
    missing = [member_id for member_id in bill.participants if member_id not in stays]
    if bill.payer_id is not None and bill.payer_id not in stays:
        missing.append(bill.payer_id)
    if missing:
        raise AppError(
            "STAY_NOT_FOUND", "参与人或垫付人在此账本没有入住记录",
            status_code=422, field="participants",
        )


def calculate_shares(bill: Bill, stays: Mapping[int, Stay]) -> list[ShareDetail]:
    validate_members(bill, stays)
    try:
        shares = split_bill(bill, stays)
    except (ValueError, KeyError) as exc:
        raise AppError("INVALID_SPLIT", str(exc), status_code=422) from exc
    if sum(item.share_cents for item in shares) != bill.amount_cents:
        raise AppError("INVALID_SPLIT", "分摊金额与账单金额不一致", status_code=422)
    return shares
