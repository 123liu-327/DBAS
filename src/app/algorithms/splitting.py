"""Pure integer-cent bill splitting; participant order resolves remainder ties."""

from collections.abc import Mapping
from datetime import date

from app.models.bill import Bill, SplitMethod
from app.models.share import ShareDetail
from app.models.stay import Stay


def overlap_days(start: date, end: date, stay: Stay) -> int:
    last = min(end, stay.leave_date or end)
    first = max(start, stay.join_date)
    return max(0, (last - first).days + 1)


def allocate_cents(amount_cents: int, weights: list[int]) -> list[int]:
    total = sum(weights)
    if amount_cents <= 0 or total <= 0 or any(weight < 0 for weight in weights):
        raise ValueError("Amount and total weight must be positive; weights cannot be negative")
    parts = [divmod(amount_cents * weight, total) for weight in weights]
    shares = [quotient for quotient, _ in parts]
    remaining = amount_cents - sum(shares)
    priority = sorted(range(len(weights)), key=lambda index: (-parts[index][1], index))
    for index in priority[:remaining]:
        shares[index] += 1
    return shares


def split_bill(bill: Bill, stays: Mapping[int, Stay]) -> list[ShareDetail]:
    if bill.amount_cents is None or bill.method is None or not bill.participants:
        raise ValueError("A complete bill is required")
    if any(member_id not in stays for member_id in bill.participants):
        raise ValueError("All participants must exist in the book")
    if bill.method == SplitMethod.EVEN:
        weights = [1] * len(bill.participants)
    elif bill.method == SplitMethod.BY_DAYS:
        if bill.period is None:
            raise ValueError("BY_DAYS requires a period")
        weights = [
            overlap_days(bill.period.start, bill.period.end, stays[member_id])
            for member_id in bill.participants
        ]
    else:
        if bill.weights is None:
            raise ValueError("BY_WEIGHT requires weights")
        weights = [bill.weights[member_id] for member_id in bill.participants]

    shares = allocate_cents(bill.amount_cents, weights)
    return [
        ShareDetail(
            bill_id=bill.id,
            member_id=member_id,
            share_cents=shares[index],
            effective_days=weights[index] if bill.method == SplitMethod.BY_DAYS else None,
            weight=weights[index] if bill.method == SplitMethod.BY_WEIGHT else None,
        )
        for index, member_id in enumerate(bill.participants)
    ]
