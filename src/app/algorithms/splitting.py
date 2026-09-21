"""Pure integer-cent bill splitting; participant order resolves remainder ties."""

from collections.abc import Mapping
from datetime import date

from app.models.bill import Bill, SplitMethod
from app.models.share import ShareDetail
from app.models.stay import Stay


# 以下为待手写区域：overlap_days（现有实现为参考，实际改写后再标记为手写）
def overlap_days(start: date, end: date, stay: Stay) -> int:
    last = min(end, stay.leave_date or end)
    first = max(start, stay.join_date)
    return max(0, (last - first).days + 1)
# 待手写区域结束：overlap_days


# 以下为待手写区域：allocate_cents（现有实现为参考，实际改写后再标记为手写）
def allocate_cents(amount_cents: int, weights: list[int]) -> list[int]:
    total = sum(weights)
    if amount_cents <= 0 or total <= 0 or any(weight < 0 for weight in weights):
        raise ValueError("账单金额和总权重必须为正数，单项权重不能为负数")
    parts = [divmod(amount_cents * weight, total) for weight in weights]
    shares = [quotient for quotient, _ in parts]
    remaining = amount_cents - sum(shares)
    priority = sorted(range(len(weights)), key=lambda index: (-parts[index][1], index))
    for index in priority[:remaining]:
        shares[index] += 1
    return shares
# 待手写区域结束：allocate_cents


# 以下为待手写区域：split_bill（现有实现为参考，实际改写后再标记为手写）
def split_bill(bill: Bill, stays: Mapping[int, Stay]) -> list[ShareDetail]:
    if bill.amount_cents is None or bill.method is None or not bill.participants:
        raise ValueError("账单信息不完整，无法计算分摊")
    if any(member_id not in stays for member_id in bill.participants):
        raise ValueError("所有参与人都必须在当前账本中有入住记录")
    if bill.method == SplitMethod.EVEN:
        weights = [1] * len(bill.participants)
    elif bill.method == SplitMethod.BY_DAYS:
        if bill.period is None:
            raise ValueError("按天分摊必须提供分摊周期")
        weights = [
            overlap_days(bill.period.start, bill.period.end, stays[member_id])
            for member_id in bill.participants
        ]
    else:
        if bill.weights is None:
            raise ValueError("按权重分摊必须提供权重")
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
# 待手写区域结束：split_bill
