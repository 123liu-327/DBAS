from datetime import UTC, date, datetime

import pytest
from pydantic import ValidationError

from app.models import Bill, BillStatus, Book, Member, SettlementSnapshot, SplitMethod, Stay


def posted_bill(**changes: object) -> Bill:
    values: dict[str, object] = {
        "id": "bill_1",
        "bookId": 1,
        "title": "电费",
        "amountCents": 10000,
        "date": "2026-03-28",
        "method": "EVEN",
        "participants": [1, 2],
        "payerId": 1,
        "status": "POSTED",
    }
    values.update(changes)
    return Bill.model_validate(values)


def test_timestamps_are_equal_at_creation_and_use_camel_case() -> None:
    book = Book(id=1, name="3栋402")
    assert book.created_at == book.updated_at
    assert book.created_at.tzinfo is not None
    dumped = book.model_dump(mode="json")
    assert "createdAt" in dumped and "updatedAt" in dumped
    assert "created_at" not in dumped
    updated = Book(
        id=1, name="3栋402", createdAt=book.created_at, updatedAt=datetime.now(UTC)
    )
    assert updated.updated_at >= updated.created_at
    changed = book.with_updates(name="3栋403")
    assert changed.created_at == book.created_at
    assert changed.updated_at >= book.updated_at
    assert changed.name == "3栋403"
    with pytest.raises(ValueError):
        book.with_updates(created_at=datetime.now(UTC))
    with pytest.raises(ValidationError):
        Book(id=1, name="3栋402", createdAt=datetime.now(UTC))


def test_member_stay_dates_and_name() -> None:
    member = Member(id=1, name="张三")
    stay = Stay(bookId=1, memberId=member.id, joinDate="2026-01-01", leaveDate=None)
    assert stay.join_date == date(2026, 1, 1)
    with pytest.raises(ValidationError):
        Stay(bookId=1, memberId=2, joinDate="2026-02-01", leaveDate="2026-01-31")
    with pytest.raises(ValidationError):
        Member(id=2, name="a" * 11)


def test_draft_can_be_incomplete_but_posted_cannot() -> None:
    assert {status.value for status in BillStatus} == {
        "DRAFT", "POSTED", "LOCKED", "SETTLED",
    }
    draft = Bill(id="b1", bookId=1)
    assert draft.status == BillStatus.DRAFT
    with pytest.raises(ValidationError):
        Bill(id="b1", bookId=1, status="POSTED")
    assert posted_bill().method == SplitMethod.EVEN
    with pytest.raises(ValidationError):
        posted_bill(status="UNKNOWN")


@pytest.mark.parametrize("amount", [0, -1, 1.5, True])
def test_amount_must_be_positive_integer_cents(amount: object) -> None:
    with pytest.raises(ValidationError):
        posted_bill(amountCents=amount)


def test_participants_and_payer() -> None:
    with pytest.raises(ValidationError):
        posted_bill(participants=[1, 1])
    with pytest.raises(ValidationError):
        posted_bill(payerId=3)
    with pytest.raises(ValidationError):
        posted_bill(participants=[])


def test_method_specific_fields() -> None:
    with pytest.raises(ValidationError):
        posted_bill(method="BY_DAYS")
    with pytest.raises(ValidationError):
        posted_bill(method="BY_DAYS", period={"start": "2026-04-01", "end": "2026-03-01"})
    assert posted_bill(
        method="BY_DAYS", period={"start": "2026-03-01", "end": "2026-03-31"}
    ).period is not None
    with pytest.raises(ValidationError):
        posted_bill(method="BY_WEIGHT", weights={"1": 2})
    with pytest.raises(ValidationError):
        posted_bill(method="BY_WEIGHT", weights={"1": 2, "2": 0})
    assert posted_bill(method="BY_WEIGHT", weights={"1": 2, "2": 1}).weights == {
        1: 2, 2: 1
    }


def test_settlement_snapshot_structure() -> None:
    snapshot = SettlementSnapshot(
        id="s1", bookId=1, startMonth="2026-03", endMonth="2026-03",
        billIds=["b1"], balances=[
            {"memberId": 1, "paidCents": 100, "shareCents": 50, "netCents": 50},
            {"memberId": 2, "paidCents": 0, "shareCents": 50, "netCents": -50},
        ],
        transfers=[{"fromMemberId": 2, "toMemberId": 1, "amountCents": 50}],
        confirmations=[{"memberId": 1}, {"memberId": 2}],
    )
    assert snapshot.model_dump(mode="json")["status"] == "LOCKED"
