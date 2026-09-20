from datetime import date

import pytest

from app.algorithms.splitting import allocate_cents, overlap_days, split_bill
from app.models.bill import Bill
from app.models.stay import Stay
from app.services.splitting_service import calculate_shares


@pytest.mark.parametrize(
    ("amount", "weights", "expected"),
    [
        (60000, [1, 1, 1], [20000, 20000, 20000]),
        (10000, [1, 1, 1], [3334, 3333, 3333]),
        (10000, [1, 1, 1, 1], [2500, 2500, 2500, 2500]),
        (10001, [1, 1, 1, 1], [2501, 2500, 2500, 2500]),
        (6200, [31, 31], [3100, 3100]),
        (6200, [31, 21, 31], [2316, 1569, 2315]),
        (7000, [10, 30, 30], [1000, 3000, 3000]),
        (5000, [0, 10, 10], [0, 2500, 2500]),
        (5000, [2, 1], [3333, 1667]),
        (4000, [3, 1], [3000, 1000]),
    ],
)
def test_official_t01_to_t10(amount: int, weights: list[int], expected: list[int]) -> None:
    assert allocate_cents(amount, weights) == expected
    assert sum(expected) == amount


def test_inclusive_stay_dates_and_live_recalculation() -> None:
    members = {
        1: Stay(bookId=1, memberId=1, joinDate="2026-03-01"),
        2: Stay(bookId=1, memberId=2, joinDate="2026-03-11"),
        3: Stay(bookId=1, memberId=3, joinDate="2026-03-01"),
    }
    bill = Bill(
        id="b1", bookId=1, title="电费", amountCents=6200, date="2026-03-31",
        method="BY_DAYS", participants=list(members), payerId=1, status="POSTED",
        period={"start": "2026-03-01", "end": "2026-03-31"},
    )
    assert overlap_days(date(2026, 3, 1), date(2026, 3, 31), members[2]) == 21
    assert [item.share_cents for item in split_bill(bill, members)] == [2316, 1569, 2315]
    members[2] = members[2].with_updates(join_date=date(2026, 3, 1))
    assert [item.share_cents for item in split_bill(bill, members)] == [2067, 2067, 2066]


def test_all_zero_days_are_invalid() -> None:
    with pytest.raises(ValueError):
        allocate_cents(100, [0, 0])


@pytest.mark.parametrize(
    ("amount", "method", "stays", "period", "weights", "expected"),
    [
        (60000, "EVEN", [None] * 3, None, None, [20000, 20000, 20000]),
        (10000, "EVEN", [None] * 3, None, None, [3334, 3333, 3333]),
        (10000, "EVEN", [None] * 4, None, None, [2500] * 4),
        (10001, "EVEN", [None] * 4, None, None, [2501, 2500, 2500, 2500]),
        (6200, "BY_DAYS", [None] * 2, ("2026-03-01", "2026-03-31"), None,
         [3100, 3100]),
        (6200, "BY_DAYS", [None, ("2026-03-11", None), None],
         ("2026-03-01", "2026-03-31"), None, [2316, 1569, 2315]),
        (7000, "BY_DAYS", [("2026-03-01", "2026-03-10"), None, None],
         ("2026-03-01", "2026-03-30"), None, [1000, 3000, 3000]),
        (5000, "BY_DAYS", [("2026-03-11", None), None, None],
         ("2026-03-01", "2026-03-10"), None, [0, 2500, 2500]),
        (5000, "BY_WEIGHT", [None] * 2, None, [2, 1], [3333, 1667]),
        (4000, "BY_WEIGHT", [None] * 2, None, [3, 1], [3000, 1000]),
    ],
)
def test_official_t01_to_t10_through_complete_bills(
    amount: int, method: str, stays: list[tuple[str, str | None] | None],
    period: tuple[str, str] | None, weights: list[int] | None, expected: list[int],
) -> None:
    members = {}
    for index, stay in enumerate(stays):
        join, leave = stay or ("2026-03-01", None)
        members[index + 1] = Stay(
            bookId=1, memberId=index + 1, joinDate=join, leaveDate=leave,
        )
    values = {
        "id": "bill_1", "bookId": 1, "title": "测试账单",
        "amountCents": amount, "date": "2026-03-31", "method": method,
        "participants": list(members), "payerId": 1, "status": "POSTED",
    }
    if period is not None:
        values["period"] = {"start": period[0], "end": period[1]}
    if weights is not None:
        values["weights"] = {str(index + 1): weight for index, weight in enumerate(weights)}
    shares = calculate_shares(Bill.model_validate(values), members)
    assert [item.share_cents for item in shares] == expected
    assert sum(item.share_cents for item in shares) == amount
